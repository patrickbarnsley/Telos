<#
.SYNOPSIS
  Deploy Telos to AWS: a Graviton EC2 instance running Docker and Caddy, and
  the landing page on S3 + CloudFront.

.DESCRIPTION
  Run the steps in order. Each is idempotent; re-running is safe.

    .\deploy.ps1 -Step dns        # once; then point your registrar's nameservers
    .\deploy.ps1 -Step secrets    # once, and again whenever a secret changes
    .\deploy.ps1 -Step site       # landing page stack + upload
    .\deploy.ps1 -Step app        # build, push, deploy the app stack
    .\deploy.ps1 -Step release    # rebuild + push + roll the service (routine)
    .\deploy.ps1 -Step status     # where everything stands
    .\deploy.ps1 -Step logs       # recent application logs
    .\deploy.ps1 -Step destroy    # tear it all down

.NOTES
  Requires AWS CLI v2 and an AWS profile with rights to
  create VPC, EC2, ACM, Route 53, S3, CloudFront, IAM and SSM resources.
  Docker is NOT needed locally - the image is built on the instance.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('dns', 'secrets', 'site', 'app', 'release', 'status', 'logs', 'destroy')]
    [string]$Step,

    [string]$Domain      = 'usetelosapp.com',
    [string]$Region      = 'us-east-1',
    [string]$Profile     = 'default',
    [string]$ImageTag    = (Get-Date -Format 'yyyyMMdd-HHmmss'),

    # secrets step: read values from a file instead of prompting. Accepts .env
    # style (KEY=value) or TOML style (KEY = "value"), so a block copied
    # straight out of Streamlit Cloud's secrets panel works as-is.
    [string]$EnvFile     = '',
    [string]$RepoRoot    = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

$ErrorActionPreference = 'Stop'

# The AWS CLI is a Python program and writes to the console using the Windows
# ANSI code page by default. Any non-ANSI character in a response - an arrow in
# cloud-init output, an emoji in application logs - makes it die with a
# 'charmap codec can't encode character' error instead of printing. Forcing
# UTF-8 for its output avoids that entirely.
$env:PYTHONIOENCODING = 'utf-8'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }

$DnsStack  = 'telos-dns'
$SiteStack = 'telos-site'
$AppStack  = 'telos-app'

function Say  { param($m) Write-Host "`n=== $m" -ForegroundColor Cyan }
function Ok   { param($m) Write-Host "  $m" -ForegroundColor Green }
function Warn { param($m) Write-Host "  $m" -ForegroundColor Yellow }

# Resolve the real AWS CLI executable once.
#
# This MUST target aws.exe rather than the bare name 'aws'. PowerShell function
# names are case-insensitive, so a function named Aws whose body calls 'aws'
# calls itself, recursing until the interpreter aborts with a call depth
# overflow. Binding to the Application command avoids the collision entirely.
$script:AwsExe = $null
function Get-AwsExe {
    if (-not $script:AwsExe) {
        $cmd = Get-Command aws.exe -CommandType Application -ErrorAction SilentlyContinue |
               Select-Object -First 1
        if (-not $cmd) { throw 'AWS CLI v2 not found on PATH. Install: https://aws.amazon.com/cli/' }
        $script:AwsExe = $cmd.Source
    }
    return $script:AwsExe
}

function Aws {
    # $ErrorActionPreference is 'Stop' for this script, and in Windows PowerShell
    # that promotes ANY stderr output from a native command into a terminating
    # error. The AWS CLI writes to stderr routinely and harmlessly - looking up a
    # parameter that does not exist yet, for instance - so that default would
    # abort the script on entirely normal conditions. Success is judged by
    # $LASTEXITCODE at each call site instead.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try   { & (Get-AwsExe) @args --region $Region --profile $Profile }
    finally { $ErrorActionPreference = $prev }
}

function Require-Tool {
    param($Name, $Hint)
    # -CommandType Application so this finds the real binary and never matches a
    # same-named function defined in this script.
    if (-not (Get-Command $Name -CommandType Application -ErrorAction SilentlyContinue)) {
        throw "$Name not found on PATH. $Hint"
    }
}

function Get-StackOutput {
    param($Stack, $Key)
    $v = Aws cloudformation describe-stacks --stack-name $Stack `
            --query "Stacks[0].Outputs[?OutputKey=='$Key'].OutputValue" --output text 2>&1
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($v) -or $v -eq 'None') { return $null }
    return $v.Trim()
}

function Require-HostedZone {
    $id = Get-StackOutput $DnsStack 'HostedZoneId'
    if (-not $id) { throw "Hosted zone not found. Run: .\deploy.ps1 -Step dns" }
    return $id
}

function Invoke-Release {
    <#
      Ships source to S3 and asks the instance to rebuild via SSM Run Command.

      No Docker on your machine, no ECR, and no cross-compiling for ARM: the
      image is built natively on the Graviton instance. No SSH either - Run
      Command reaches the box through the SSM agent.
    #>
    $bucket   = Get-StackOutput $AppStack 'DeployBucketName'
    $instance = Get-StackOutput $AppStack 'InstanceId'
    if (-not $bucket -or -not $instance) { throw "App stack not deployed yet. Run: .\deploy.ps1 -Step app" }

    # CloudFormation reports the instance complete the moment it boots, but the
    # UserData bootstrap - dnf update, Docker, Compose, writing /opt/telos - runs
    # for several minutes after that. Sending the deploy before it finishes fails
    # with 'No such file or directory'. Wait for the bootstrap to land.
    Say 'Waiting for the instance to finish setting itself up'
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        $probe = Aws ssm send-command --instance-ids $instance `
                    --document-name 'AWS-RunShellScript' `
                    --parameters 'commands=["test -x /opt/telos/deploy.sh && echo READY || echo WAITING"]' `
                    --query 'Command.CommandId' --output text 2>&1
        if ($LASTEXITCODE -eq 0 -and $probe) {
            Start-Sleep -Seconds 6
            $out = Aws ssm get-command-invocation --command-id $probe --instance-id $instance `
                       --query 'StandardOutputContent' --output text 2>&1
            if ($out -match 'READY') { $ready = $true; break }
        }
        Write-Host '.' -NoNewline
        Start-Sleep -Seconds 10
    }
    Write-Host ''
    if (-not $ready) {
        throw "The instance never finished its bootstrap. Check the log with:`n  aws ssm start-session --target $instance --region $Region`n  then: sudo tail -50 /var/log/telos-bootstrap.log"
    }
    Ok 'Instance ready'

    $staging = Join-Path $env:TEMP "telos-bundle-$(Get-Random)"
    $zipPath = Join-Path $env:TEMP "telos-app-$(Get-Random).zip"
    New-Item -ItemType Directory -Path $staging -Force | Out-Null
    try {
        foreach ($item in @('app.py', 'requirements.txt', 'Dockerfile')) {
            Copy-Item (Join-Path $RepoRoot $item) $staging -Force
        }
        foreach ($dir in @('core', 'pages', '.streamlit')) {
            Copy-Item (Join-Path $RepoRoot $dir) $staging -Recurse -Force
        }
        # Never ship caches or local secrets to the server.
        Get-ChildItem $staging -Recurse -Force -Include '__pycache__', '*.pyc', '.env', 'secrets.toml' |
            Remove-Item -Recurse -Force -ErrorAction SilentlyContinue

        # Compress-Archive is not usable here. Windows PowerShell 5.1 writes
        # backslashes as the path separator inside the archive, which the ZIP
        # spec forbids; Linux unzip warns and exits 1, and deploy.sh runs under
        # set -e, so the whole deploy aborts. Building the archive through
        # System.IO.Compression lets the entry names be set explicitly, with
        # forward slashes.
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $archive = [System.IO.Compression.ZipFile]::Open($zipPath, 'Create')
        try {
            $root = (Resolve-Path $staging).Path.TrimEnd('\')
            foreach ($file in Get-ChildItem -Path $staging -Recurse -File -Force) {
                $rel = $file.FullName.Substring($root.Length + 1).Replace('\', '/')
                $null = [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                            $archive, $file.FullName, $rel)
            }
        }
        finally { $archive.Dispose() }

        $sizeKb = [math]::Round((Get-Item $zipPath).Length / 1KB)
        Ok "Bundle built ($sizeKb KB)"

        Aws s3 cp $zipPath "s3://$bucket/app.zip"
        if ($LASTEXITCODE -ne 0) { throw 'Upload to S3 failed.' }
        Ok 'Uploaded'

        Say 'Building and restarting on the instance'
        $cmdId = Aws ssm send-command `
            --instance-ids $instance `
            --document-name 'AWS-RunShellScript' `
            --comment 'Telos deploy' `
            --parameters 'commands=["/opt/telos/deploy.sh"]' `
            --timeout-seconds 900 `
            --query 'Command.CommandId' --output text
        if ($LASTEXITCODE -ne 0 -or -not $cmdId) { throw 'Could not send the deploy command. Is the instance registered with SSM yet? It takes a few minutes after first boot.' }

        Write-Host '  Building the image on the instance (first run 5-8 min)' -NoNewline
        $status = 'Pending'
        for ($i = 0; $i -lt 120; $i++) {
            Start-Sleep -Seconds 10
            Write-Host '.' -NoNewline
            $status = (Aws ssm get-command-invocation --command-id $cmdId --instance-id $instance `
                        --query 'Status' --output text 2>$null)
            if ($status -in @('Success', 'Failed', 'TimedOut', 'Cancelled')) { break }
        }
        Write-Host ''
        if ($status -ne 'Success') {
            Warn "Deploy command finished with status: $status"
            Warn 'Output follows:'
            Aws ssm get-command-invocation --command-id $cmdId --instance-id $instance `
                --query 'StandardErrorContent' --output text
            throw 'Deploy failed on the instance.'
        }
        Ok 'Application rebuilt and running'
    }
    finally {
        Remove-Item $staging -Recurse -Force -ErrorAction SilentlyContinue
        Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
    }
}

Require-Tool aws.exe 'Install AWS CLI v2: https://aws.amazon.com/cli/'
$AccountId = (Aws sts get-caller-identity --query Account --output text).Trim()
if (-not $AccountId) { throw 'Could not resolve AWS account. Check your credentials.' }

switch ($Step) {

# ---------------------------------------------------------------------- dns
'dns' {
    Say 'Creating the Route 53 hosted zone'
    Aws cloudformation deploy `
        --stack-name $DnsStack `
        --template-file (Join-Path $RepoRoot 'infra\telos-dns.yaml') `
        --parameter-overrides "DomainName=$Domain"

    $ns = Get-StackOutput $DnsStack 'Nameservers'
    Ok "Hosted zone created for $Domain"
    Write-Host ''
    Warn 'ACTION REQUIRED - set these four nameservers at your registrar:'
    $ns -split ',\s*' | ForEach-Object { Write-Host "    $_" -ForegroundColor White }
    Write-Host ''
    Warn 'Then WAIT for propagation before running -Step site or -Step app.'
    Warn 'Both request DNS-validated certificates; if the nameservers are not'
    Warn 'live yet those stacks hang until they time out. Verify first with:'
    Write-Host "    nslookup -type=NS $Domain" -ForegroundColor White
}

# ------------------------------------------------------------------ secrets
'secrets' {
    Say 'Writing application secrets to SSM Parameter Store'

    $keys = @('ANTHROPIC_API_KEY', 'DATABASE_URL', 'SUPABASE_URL',
              'SUPABASE_ANON_KEY', 'ADMIN_PASSWORD', 'OWNER_EMAILS')

    $prompts = @{
        ANTHROPIC_API_KEY = 'Anthropic API key'
        DATABASE_URL      = 'Postgres connection string (Supabase)'
        SUPABASE_URL      = 'Supabase project URL'
        SUPABASE_ANON_KEY = 'Supabase anon/publishable key'
        ADMIN_PASSWORD    = 'Admin page password'
        OWNER_EMAILS      = 'Your email (unmetered AI usage)'
    }

    function Save-Secret {
        param($Key, $Value)
        Aws ssm put-parameter --name "/telos/$Key" --value $Value --type SecureString --overwrite | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Failed to save $Key to Parameter Store." }
        Ok "$Key saved"
    }

    if ($EnvFile) {
        # ---- file mode -------------------------------------------------
        if (-not (Test-Path $EnvFile)) { throw "File not found: $EnvFile" }
        Ok "Reading from $EnvFile"

        $found = @{}
        foreach ($line in Get-Content $EnvFile) {
            $t = $line.Trim()
            if (-not $t -or $t.StartsWith('#')) { continue }
            # KEY=value  and  KEY = "value"  both parse here
            if ($t -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$') {
                $k = $matches[1].Trim()
                $v = $matches[2].Trim().Trim('"').Trim("'")
                if ($keys -contains $k -and $v) { $found[$k] = $v }
            }
        }

        if ($found.Count -eq 0) { throw "No recognised keys found in $EnvFile. Expected: $($keys -join ', ')" }

        foreach ($k in $keys) {
            if ($found.ContainsKey($k)) { Save-Secret $k $found[$k] }
            else { Warn "$k not in file - the app will not start without it" }
        }

        Write-Host ''
        Warn 'That file holds your secrets in plain text. Delete it now:'
        Write-Host "    Remove-Item '$EnvFile'" -ForegroundColor White
    }
    else {
        # ---- prompt mode -----------------------------------------------
        Write-Host '  Stored as SecureString. Parameter Store standard tier is free;'
        Write-Host '  Secrets Manager would be $0.40 per secret per month.'
        Write-Host '  Press Enter to leave an existing value unchanged.'
        Write-Host '  Typing is masked, so nothing appears on screen as you type.'
        Write-Host ''
        Write-Host '  Faster alternative: put the values in a file and run'
        Write-Host '    .\deploy\deploy.ps1 -Step secrets -EnvFile .\telos-secrets.txt' -ForegroundColor White
        Write-Host ''

        foreach ($k in $keys) {
            $null = Aws ssm get-parameter --name "/telos/$k" --query 'Parameter.Name' --output text 2>&1
            $exists = ($LASTEXITCODE -eq 0)
            $label = if ($exists) { "$($prompts[$k]) [already set]" } else { "$($prompts[$k]) [not set]" }

            $secure = Read-Host -Prompt "  $label" -AsSecureString
            $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
                        [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))

            if ([string]::IsNullOrWhiteSpace($plain)) {
                if (-not $exists) { Warn "    $k is still unset - the app will not start without it" }
                continue
            }
            Save-Secret $k $plain
        }
    }

    Say 'Verifying'
    $missing = @()
    foreach ($k in $keys) {
        $null = Aws ssm get-parameter --name "/telos/$k" --query 'Parameter.Name' --output text 2>&1
        if ($LASTEXITCODE -ne 0) { $missing += $k }
    }
    if ($missing.Count -gt 0) { Warn "Still missing: $($missing -join ', ')" }
    else { Ok "All $($keys.Count) secrets are stored" }
}

# --------------------------------------------------------------------- site
'site' {
    $zone = Require-HostedZone
    Say 'Deploying the landing page stack (S3 + CloudFront)'
    Warn 'Certificate validation can take several minutes on first run.'
    Aws cloudformation deploy `
        --stack-name $SiteStack `
        --template-file (Join-Path $RepoRoot 'infra\telos-site.yaml') `
        --parameter-overrides "DomainName=$Domain" "HostedZoneId=$zone"

    $bucket = Get-StackOutput $SiteStack 'BucketName'
    $dist   = Get-StackOutput $SiteStack 'DistributionId'
    $page   = Join-Path $RepoRoot 'telos-site\index.html'
    if (-not (Test-Path $page)) { throw "Landing page not found at $page" }

    Say 'Uploading index.html'
    Aws s3 cp $page "s3://$bucket/index.html" --content-type 'text/html; charset=utf-8' --cache-control 'public, max-age=300'
    Ok "Uploaded to $bucket"

    Say 'Invalidating the CloudFront cache'
    Aws cloudfront create-invalidation --distribution-id $dist --paths '/*' --query 'Invalidation.Id' --output text | Out-Null
    Ok "Live at https://$Domain (allow a few minutes on first deploy)"
}

# ---------------------------------------------------------------------- app
'app' {
    $zone = Require-HostedZone

    Say 'Deploying the application stack (VPC, EC2, Elastic IP, DNS)'
    Warn 'First run takes about 5 minutes.'
    Aws cloudformation deploy `
        --stack-name $AppStack `
        --template-file (Join-Path $RepoRoot 'infra\telos-app.yaml') `
        --capabilities CAPABILITY_IAM `
        --parameter-overrides `
            "DomainName=$Domain" `
            "HostedZoneId=$zone"

    Ok "Instance:  $(Get-StackOutput $AppStack 'InstanceId')"
    Ok "Public IP: $(Get-StackOutput $AppStack 'PublicIp')"

    Say 'Shipping the application code'
    Invoke-Release

    Write-Host ''
    Ok (Get-StackOutput $AppStack 'AppUrl')
    Warn 'Caddy needs a minute or two to obtain the TLS certificate on first run.'
    Warn 'A browser warning during that window is expected. Give it 5 minutes.'
}

# ------------------------------------------------------------------ release
'release' {
    Say 'Shipping the application code'
    Invoke-Release
    Ok (Get-StackOutput $AppStack 'AppUrl')
}

# ------------------------------------------------------------------- status
'status' {
    Say 'Stacks'
    foreach ($s in @($DnsStack, $SiteStack, $AppStack)) {
        $st = Aws cloudformation describe-stacks --stack-name $s --query 'Stacks[0].StackStatus' --output text 2>$null
        if ($LASTEXITCODE -eq 0) { Ok "$s : $st" } else { Warn "$s : not deployed" }
    }

    $instance = Get-StackOutput $AppStack 'InstanceId'
    if ($instance) {
        Say 'Instance'
        Aws ec2 describe-instances --instance-ids $instance `
            --query 'Reservations[0].Instances[0].{state:State.Name,type:InstanceType,ip:PublicIpAddress,launched:LaunchTime}' `
            --output table

        Say 'Containers'
        $cmdId = Aws ssm send-command --instance-ids $instance `
            --document-name 'AWS-RunShellScript' `
            --parameters 'commands=["cd /opt/telos && docker compose ps"]' `
            --query 'Command.CommandId' --output text 2>$null
        if ($cmdId) {
            Start-Sleep -Seconds 5
            Aws ssm get-command-invocation --command-id $cmdId --instance-id $instance `
                --query 'StandardOutputContent' --output text 2>$null
        } else {
            Warn 'Could not reach the instance over SSM.'
        }
    }

    $url = Get-StackOutput $AppStack 'AppUrl'
    if ($url) { Say 'URLs'; Ok "App:  $url"; Ok "Site: https://$Domain" }

    if ($instance) {
        Write-Host ''
        Write-Host "  Shell:  aws ssm start-session --target $instance --region $Region" -ForegroundColor White
        Write-Host "  Logs:   .\deploy\deploy.ps1 -Step logs" -ForegroundColor White
    }
}

# --------------------------------------------------------------------- logs
'logs' {
    $instance = Get-StackOutput $AppStack 'InstanceId'
    if (-not $instance) { throw 'App stack not deployed.' }
    Say 'Last 80 lines from the application container'
    $cmdId = Aws ssm send-command --instance-ids $instance `
        --document-name 'AWS-RunShellScript' `
        --parameters 'commands=["cd /opt/telos && docker compose logs --tail 80 telos"]' `
        --query 'Command.CommandId' --output text
    Start-Sleep -Seconds 6
    Aws ssm get-command-invocation --command-id $cmdId --instance-id $instance `
        --query 'StandardOutputContent' --output text
    Write-Host ''
    Write-Host "  Live tail:  aws ssm start-session --target $instance --region $Region" -ForegroundColor White
    Write-Host "              then: cd /opt/telos && docker compose logs -f telos" -ForegroundColor White
}

# ------------------------------------------------------------------ destroy
'destroy' {
    Warn "This deletes the Telos AWS infrastructure for $Domain."
    Warn 'The S3 bucket is retained on purpose and must be emptied and deleted by hand.'
    $confirm = Read-Host '  Type DESTROY to continue'
    if ($confirm -ne 'DESTROY') { Warn 'Cancelled.'; break }

    foreach ($s in @($AppStack, $SiteStack)) {
        Say "Deleting $s"
        Aws cloudformation delete-stack --stack-name $s
        Aws cloudformation wait stack-delete-complete --stack-name $s
        Ok "$s deleted"
    }
    Warn "Hosted zone ($DnsStack) left in place so DNS keeps resolving."
    Warn 'Delete it manually if you are done with the domain.'
}

}

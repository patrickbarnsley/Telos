<#
.SYNOPSIS
  Deploy Telos to AWS: ECR image, ECS Fargate service behind an ALB, and the
  landing page on S3 + CloudFront.

.DESCRIPTION
  Run the steps in order. Each is idempotent — re-running is safe.

    .\deploy.ps1 -Step dns        # once; then point your registrar's nameservers
    .\deploy.ps1 -Step secrets    # once, and again whenever a secret changes
    .\deploy.ps1 -Step site       # landing page stack + upload
    .\deploy.ps1 -Step app        # build, push, deploy the app stack
    .\deploy.ps1 -Step release    # rebuild + push + roll the service (routine)
    .\deploy.ps1 -Step status     # where everything stands
    .\deploy.ps1 -Step destroy    # tear it all down

.NOTES
  Requires AWS CLI v2 and Docker Desktop, and an AWS profile with rights to
  create VPC, ECS, ELB, ACM, Route 53, S3, CloudFront, IAM and SSM resources.
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('dns', 'secrets', 'site', 'app', 'release', 'status', 'destroy')]
    [string]$Step,

    [string]$Domain      = 'usetelosapp.com',
    [string]$Region      = 'us-east-1',
    [string]$Profile     = 'default',
    [string]$ImageTag    = (Get-Date -Format 'yyyyMMdd-HHmmss'),
    [string]$RepoRoot    = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
)

$ErrorActionPreference = 'Stop'

$DnsStack  = 'telos-dns'
$SiteStack = 'telos-site'
$AppStack  = 'telos-app'
$EcrRepo   = 'telos'

function Say  { param($m) Write-Host "`n=== $m" -ForegroundColor Cyan }
function Ok   { param($m) Write-Host "  $m" -ForegroundColor Green }
function Warn { param($m) Write-Host "  $m" -ForegroundColor Yellow }

function Aws { aws @args --region $Region --profile $Profile }

function Require-Tool {
    param($Name, $Hint)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name not found on PATH. $Hint"
    }
}

function Get-StackOutput {
    param($Stack, $Key)
    $v = Aws cloudformation describe-stacks --stack-name $Stack `
            --query "Stacks[0].Outputs[?OutputKey=='$Key'].OutputValue" --output text 2>$null
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($v) -or $v -eq 'None') { return $null }
    return $v.Trim()
}

function Require-HostedZone {
    $id = Get-StackOutput $DnsStack 'HostedZoneId'
    if (-not $id) { throw "Hosted zone not found. Run: .\deploy.ps1 -Step dns" }
    return $id
}

Require-Tool aws 'Install AWS CLI v2: https://aws.amazon.com/cli/'
$AccountId = (Aws sts get-caller-identity --query Account --output text).Trim()
if (-not $AccountId) { throw 'Could not resolve AWS account. Check your credentials.' }
$Registry = "$AccountId.dkr.ecr.$Region.amazonaws.com"

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
    Warn 'ACTION REQUIRED — set these four nameservers at your registrar:'
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
    Write-Host '  Stored as SecureString. Parameter Store standard tier is free;'
    Write-Host '  Secrets Manager would be $0.40 per secret per month.'
    Write-Host '  Press Enter to leave an existing value unchanged.'
    Write-Host ''

    $names = @(
        @{ Key = 'ANTHROPIC_API_KEY'; Prompt = 'Anthropic API key' },
        @{ Key = 'DATABASE_URL';      Prompt = 'Postgres connection string (Supabase)' },
        @{ Key = 'SUPABASE_URL';      Prompt = 'Supabase project URL' },
        @{ Key = 'SUPABASE_ANON_KEY'; Prompt = 'Supabase anon/publishable key' },
        @{ Key = 'ADMIN_PASSWORD';    Prompt = 'Admin page password' },
        @{ Key = 'OWNER_EMAILS';      Prompt = 'Your email (unmetered AI usage)' }
    )

    foreach ($n in $names) {
        $path = "/telos/$($n.Key)"
        $exists = $null -ne (Aws ssm get-parameter --name $path --query 'Parameter.Name' --output text 2>$null)
        $label = if ($exists) { "$($n.Prompt) [already set]" } else { "$($n.Prompt) [not set]" }
        $secure = Read-Host -Prompt "  $label" -AsSecureString
        $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto(
                    [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
        if ([string]::IsNullOrWhiteSpace($plain)) {
            if (-not $exists) { Warn "    $($n.Key) is still unset — the task will fail to start without it." }
            continue
        }
        Aws ssm put-parameter --name $path --value $plain --type SecureString --overwrite | Out-Null
        Ok "$($n.Key) saved"
    }
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
    Require-Tool docker 'Install Docker Desktop: https://docs.docker.com/desktop/'
    $zone = Require-HostedZone

    Say 'Ensuring the ECR repository exists'
    $null = Aws ecr describe-repositories --repository-names $EcrRepo 2>$null
    if ($LASTEXITCODE -ne 0) {
        Aws ecr create-repository --repository-name $EcrRepo `
            --image-scanning-configuration scanOnPush=true `
            --image-tag-mutability IMMUTABLE | Out-Null
        Ok 'Repository created'
    } else { Ok 'Repository already exists' }

    Say 'Logging Docker in to ECR'
    Aws ecr get-login-password | docker login --username AWS --password-stdin $Registry
    if ($LASTEXITCODE -ne 0) { throw 'ECR login failed.' }

    Say "Building the image ($ImageTag)"
    # --platform matters: Fargate here runs X86_64, and an image built on an
    # ARM machine will start and then die with "exec format error".
    docker build --platform linux/amd64 -t "${EcrRepo}:$ImageTag" $RepoRoot
    if ($LASTEXITCODE -ne 0) { throw 'Docker build failed.' }

    docker tag "${EcrRepo}:$ImageTag" "$Registry/${EcrRepo}:$ImageTag"
    Say 'Pushing to ECR'
    docker push "$Registry/${EcrRepo}:$ImageTag"
    if ($LASTEXITCODE -ne 0) { throw 'Docker push failed.' }

    Say 'Deploying the application stack (VPC, ALB, ECS Fargate)'
    Warn 'First run takes 10-15 minutes, mostly certificate validation.'
    Aws cloudformation deploy `
        --stack-name $AppStack `
        --template-file (Join-Path $RepoRoot 'infra\telos-app.yaml') `
        --capabilities CAPABILITY_IAM `
        --parameter-overrides `
            "DomainName=$Domain" `
            "HostedZoneId=$zone" `
            "ImageUri=$Registry/${EcrRepo}:$ImageTag"

    Ok (Get-StackOutput $AppStack 'AppUrl')
    Ok "ALB hostname: $(Get-StackOutput $AppStack 'LoadBalancerDns')"
}

# ------------------------------------------------------------------ release
'release' {
    Require-Tool docker 'Install Docker Desktop.'
    $zone = Require-HostedZone

    Say "Building and pushing $ImageTag"
    Aws ecr get-login-password | docker login --username AWS --password-stdin $Registry
    docker build --platform linux/amd64 -t "${EcrRepo}:$ImageTag" $RepoRoot
    if ($LASTEXITCODE -ne 0) { throw 'Docker build failed.' }
    docker tag "${EcrRepo}:$ImageTag" "$Registry/${EcrRepo}:$ImageTag"
    docker push "$Registry/${EcrRepo}:$ImageTag"
    if ($LASTEXITCODE -ne 0) { throw 'Docker push failed.' }

    Say 'Rolling the service onto the new image'
    Aws cloudformation deploy `
        --stack-name $AppStack `
        --template-file (Join-Path $RepoRoot 'infra\telos-app.yaml') `
        --capabilities CAPABILITY_IAM `
        --parameter-overrides `
            "DomainName=$Domain" `
            "HostedZoneId=$zone" `
            "ImageUri=$Registry/${EcrRepo}:$ImageTag"

    Ok 'Deployment circuit breaker is on — a failing image rolls back automatically.'
    Ok (Get-StackOutput $AppStack 'AppUrl')
}

# ------------------------------------------------------------------- status
'status' {
    Say 'Stacks'
    foreach ($s in @($DnsStack, $SiteStack, $AppStack)) {
        $st = Aws cloudformation describe-stacks --stack-name $s --query 'Stacks[0].StackStatus' --output text 2>$null
        if ($LASTEXITCODE -eq 0) { Ok "$s : $st" } else { Warn "$s : not deployed" }
    }

    $cluster = Get-StackOutput $AppStack 'ClusterName'
    $service = Get-StackOutput $AppStack 'ServiceName'
    if ($cluster -and $service) {
        Say 'ECS service'
        Aws ecs describe-services --cluster $cluster --services $service `
            --query 'services[0].{desired:desiredCount,running:runningCount,pending:pendingCount,status:status}' `
            --output table
        Say 'Recent events'
        Aws ecs describe-services --cluster $cluster --services $service `
            --query 'services[0].events[0:5].message' --output text
    }

    $url = Get-StackOutput $AppStack 'AppUrl'
    if ($url) { Say 'URLs'; Ok "App:  $url"; Ok "Site: https://$Domain" }

    $lg = Get-StackOutput $AppStack 'LogGroupName'
    if ($lg) { Write-Host "`n  Tail logs:  aws logs tail $lg --follow --region $Region" -ForegroundColor White }
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

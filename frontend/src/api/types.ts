/** Mirrors the FastAPI response shapes. Kept hand-written and small rather than
 *  generated, because the API surface is stable and a generator is another
 *  dependency to maintain for the sake of twenty endpoints. */

export type Status =
  | 'recruiter_outreach' | 'applied' | 'screening'
  | 'interview' | 'offer' | 'rejected' | 'withdrawn'

export interface Job {
  id: number
  company: string
  role: string
  status: Status
  url?: string | null
  location?: string | null
  notes?: string | null
  jd_text?: string | null
  date_applied?: string | null
  posted_salary_min?: number | null
  posted_salary_max?: number | null
}

export interface Quota { used: number; limit: number; allowed: boolean }

export interface Me {
  email: string
  plan: string
  plan_label: string
  owner: boolean
  target_role: string
  quotas: Record<string, Quota>
}

export interface Profile {
  resume_text?: string
  target_role?: string
  goals?: string | null
  resume_filename?: string | null
}

export interface ResumeVersion {
  id: number
  version_label: string
  resume_filename?: string | null
  is_active?: boolean
  created_at?: string
}

export interface MatchResult {
  id: number
  job_id?: number | null
  overall_score?: number
  summary?: string
  matched_requirements?: string[]
  missing_requirements?: string[]
  suggested_certifications?: string[]
  suggested_actions?: string[]
  company?: string | null
  role?: string | null
  created_at?: string
}

export interface PrepQuestion {
  question: string
  /** The exact line quoted from the posting that produced this question. */
  from_requirement?: string
  strength?: 'strong' | 'partial' | 'weak' | string
  /** The specific experience on this resume that answers it, addressed to the candidate. */
  how_your_resume_answers?: string
}

export interface InterviewPrep {
  questions?: PrepQuestion[]
  note?: string
  injection_attempt?: string
}

export interface Roadmap {
  target_role?: string
  summary?: string
  milestones?: { order?: number; title: string; detail?: string; why?: string }[]
}

export interface ScamVerdict {
  verdict?: 'legitimate' | 'suspicious' | 'likely_scam' | string
  confidence?: string
  summary?: string
  green_flags?: string[]
  red_flags?: string[]
}

export interface CareerPath {
  id: number
  path_name: string
  target_role: string
  goals?: string | null
}

export interface BillingState {
  plan: string
  plan_label: string
  status?: string | null
  current_period_end?: string | null
  founding_seats_left: number
  has_subscription: boolean
}

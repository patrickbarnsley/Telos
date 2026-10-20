import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Profile as P } from '../api/types'
import { ErrorNote, Panel } from '../components/ui'

export function ProfilePage() {
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['profile'], queryFn: () => api.get<P>('/api/profile') })
  const [resume, setResume] = useState<string | null>(null)
  const [target, setTarget] = useState<string | null>(null)

  const save = useMutation({
    mutationFn: () => api.put('/api/profile', {
      resume_text: resume ?? data?.resume_text ?? '',
      target_role: target ?? data?.target_role ?? '',
      goals: data?.goals ?? null,
    }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['profile'] }),
  })
  const upload = useMutation({
    mutationFn: (f: File) => {
      const form = new FormData(); form.append('file', f)
      return api.upload<{ id: number; characters: number }>('/api/resumes', form)
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['profile'] }),
  })

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Profile</h1>
          <p>Your resume and your target role. Everything else reads from these.</p>
        </div>
      </div>
      <ErrorNote error={save.error ?? upload.error} />
      <Panel title="Resume">
        <label className="field">
          <span>Upload a PDF or DOCX</span>
          <input type="file" accept=".pdf,.docx"
                 onChange={e => e.target.files?.[0] && upload.mutate(e.target.files[0])} />
        </label>
        {upload.isPending && <p className="sub">Reading that file…</p>}
        {upload.data && <p className="sub">Read {upload.data.characters.toLocaleString()} characters.</p>}
        <label className="field">
          <span>Or paste it</span>
          <textarea value={resume ?? data?.resume_text ?? ''} onChange={e => setResume(e.target.value)} />
        </label>
        <label className="field">
          <span>Target role</span>
          <input value={target ?? data?.target_role ?? ''} onChange={e => setTarget(e.target.value)} />
        </label>
        <button className="btn" disabled={save.isPending} onClick={() => save.mutate()}>
          {save.isPending ? 'Saving…' : 'Save profile'}
        </button>
      </Panel>
    </>
  )
}

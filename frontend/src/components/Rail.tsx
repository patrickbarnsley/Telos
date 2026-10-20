import { NavLink } from 'react-router-dom'
import type { Me } from '../api/types'

/** The destinations, in the order someone actually needs them. Profile is first
 *  because a new user cannot do anything until a resume exists. */
const NAV = [
  { to: '/', label: 'Pipeline', icon: '☑', end: true },
  { to: '/match', label: 'Match', icon: '◎' },
  { to: '/prep', label: 'Prep', icon: '✦' },
  { to: '/roadmap', label: 'Roadmap', icon: '⚑' },
  { to: '/advisor', label: 'Advisor', icon: '◈' },
  { to: '/profile', label: 'Profile', icon: '▣' },
]

export function Rail({ me }: { me?: Me }) {
  return (
    <nav className="rail" aria-label="Main">
      <div className="brand"><span className="mark" aria-hidden="true" />Telos</div>
      <div className="rail-label">Your campaign</div>
      {NAV.map(n => (
        <NavLink key={n.to} to={n.to} end={n.end}>
          <span className="ic" aria-hidden="true">{n.icon}</span>{n.label}
        </NavLink>
      ))}
      <div className="spacer" />
      {me && (
        <>
          <div className="rail-label">{me.plan_label}</div>
          <NavLink to="/account">
            <span className="ic" aria-hidden="true">{'◇'}</span>Account
          </NavLink>
        </>
      )}
    </nav>
  )
}

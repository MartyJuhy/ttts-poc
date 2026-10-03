export interface LivePlayerScore {
  name: string
  sets: number
  points: number
}

export interface LiveMatch {
  id: string
  group: string
  table: number
  currentSet: number
  status: 'live' | 'completed'
  version: number
  players: [LivePlayerScore, LivePlayerScore]
}

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

export const demoMatches: LiveMatch[] = [
  {
    id: 'match-1',
    group: 'A',
    table: 1,
    currentSet: 4,
    status: 'live',
    version: 0,
    players: [
      { name: 'Ladislav Novák', sets: 2, points: 8 },
      { name: 'Petr Svoboda', sets: 1, points: 6 },
    ],
  },
  {
    id: 'match-2',
    group: 'A',
    table: 2,
    currentSet: 3,
    status: 'live',
    version: 0,
    players: [
      { name: 'Jiří Dvořák', sets: 1, points: 10 },
      { name: 'Milan Král', sets: 1, points: 9 },
    ],
  },
  {
    id: 'match-3',
    group: 'B',
    table: 3,
    currentSet: 1,
    status: 'live',
    version: 0,
    players: [
      { name: 'Karel Černý', sets: 0, points: 5 },
      { name: 'Pavel Marek', sets: 0, points: 7 },
    ],
  },
]

export async function fetchMatches(): Promise<LiveMatch[]> {
  const response = await fetch(`${API_BASE_URL}/api/matches`)
  if (!response.ok) throw new Error('Unable to load matches')
  return response.json() as Promise<LiveMatch[]>
}

export async function verifyAdmin(token: string): Promise<boolean> {
  const response = await fetch(`${API_BASE_URL}/api/admin/session`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return response.ok
}

export async function changePoint(
  match: LiveMatch,
  playerIndex: number,
  delta: -1 | 1,
  token: string,
): Promise<LiveMatch> {
  const response = await fetch(`${API_BASE_URL}/api/matches/${match.id}/score`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ playerIndex, delta, expectedVersion: match.version }),
  })

  if (response.status === 409) throw new Error('score_conflict')
  if (!response.ok) throw new Error('score_update_failed')
  return response.json() as Promise<LiveMatch>
}
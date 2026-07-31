const LEVEL_RANK = { L1: 1, L2: 2, L3: 3 };
const uniq = (arr) => [...new Set(arr || [])];

export function mergeState(local, remote) {
  const L = local || {};
  const R = remote || {};
  const lp = L.progress || {};
  const rp = R.progress || {};
  const lqs = lp.quizStats || {};
  const rqs = rp.quizStats || {};
  const lf = L.favorites || {};
  const rf = R.favorites || {};

  const reviewMap = new Map();
  for (const r of [...(L.review || []), ...(R.review || [])]) {
    if (!r || !r.quizId) continue;
    const prev = reviewMap.get(r.quizId);
    if (prev) prev.cleared = prev.cleared || !!r.cleared;
    else reviewMap.set(r.quizId, { ...r, cleared: !!r.cleared });
  }

  const remoteOnboarded = !!(R.user && R.user.onboardedAt);
  const userBlock = remoteOnboarded ? (R.user || {}) : (L.user || R.user || {});

  return {
    ...L,
    ...R,
    user: { ...(L.user || {}), ...(R.user || {}), ...userBlock },
    progress: {
      ...lp,
      ...rp,
      streak: Math.max(lp.streak || 0, rp.streak || 0),
      seenCardIds: uniq([...(lp.seenCardIds || []), ...(rp.seenCardIds || [])]),
      quizStats: {
        attempts: (lqs.attempts || 0) + (rqs.attempts || 0),
        correct: (lqs.correct || 0) + (rqs.correct || 0),
      },
    },
    favorites: {
      cards: uniq([...(lf.cards || []), ...(rf.cards || [])]),
      terms: uniq([...(lf.terms || []), ...(rf.terms || [])]),
    },
    review: [...reviewMap.values()],
    difficulty: {
      ...(L.difficulty || {}),
      ...(R.difficulty || {}),
      current:
        (LEVEL_RANK[(R.difficulty || {}).current] || 0) >=
        (LEVEL_RANK[(L.difficulty || {}).current] || 0)
          ? (R.difficulty || {}).current || (L.difficulty || {}).current
          : (L.difficulty || {}).current,
    },
  };
}

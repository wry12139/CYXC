import assert from 'node:assert';
import { mergeState } from './merge.js';

// streak 取较大
assert.equal(mergeState({progress:{streak:3}}, {progress:{streak:7}}).progress.streak, 7);

// seenCardIds 并集去重
assert.deepEqual(
  mergeState({progress:{seenCardIds:['c1','c2']}}, {progress:{seenCardIds:['c2','c3']}}).progress.seenCardIds.sort(),
  ['c1','c2','c3']);

// favorites 并集
assert.deepEqual(
  mergeState({favorites:{cards:['a'],terms:['t1']}}, {favorites:{cards:['b'],terms:['t1','t2']}}).favorites.cards.sort(),
  ['a','b']);

// quizStats 累加
{
  const m = mergeState({progress:{quizStats:{attempts:4,correct:3}}}, {progress:{quizStats:{attempts:10,correct:6}}});
  assert.equal(m.progress.quizStats.attempts, 14);
  assert.equal(m.progress.quizStats.correct, 9);
}

// difficulty 取高档
assert.equal(mergeState({difficulty:{current:'L1'}}, {difficulty:{current:'L3'}}).difficulty.current, 'L3');
assert.equal(mergeState({difficulty:{current:'L2'}}, {difficulty:{current:'L1'}}).difficulty.current, 'L2');

// review 并集 + cleared OR
{
  const m = mergeState(
    {review:[{quizId:'q1',cleared:false},{quizId:'q2',cleared:false}]},
    {review:[{quizId:'q1',cleared:true},{quizId:'q3',cleared:false}]});
  const q1 = m.review.find(r=>r.quizId==='q1');
  assert.equal(q1.cleared, true);              // OR
  assert.equal(m.review.length, 3);            // q1,q2,q3
}

// user.tags 取 remote(remote 已 onboarded)
{
  const m = mergeState(
    {user:{tags:{level:'L1'},onboardedAt:null}},
    {user:{tags:{level:'L3'},onboardedAt:'2026-01-01'}});
  assert.equal(m.user.tags.level, 'L3');
}
// remote 未 onboarded 则取 local
{
  const m = mergeState(
    {user:{tags:{level:'L2'},onboardedAt:'2026-02-02'}},
    {user:{tags:{level:'L1'},onboardedAt:null}});
  assert.equal(m.user.tags.level, 'L2');
}

// 不改入参
{
  const local = {progress:{streak:1}};
  mergeState(local, {progress:{streak:9}});
  assert.equal(local.progress.streak, 1);
}

console.log('mergeState: all assertions passed');

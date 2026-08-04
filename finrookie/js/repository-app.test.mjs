import assert from 'node:assert';
import { repository } from './repository.js';

const localStorageState = new Map();
globalThis.window = {
  addEventListener() {},
  removeEventListener() {},
  Alpine: { data() {} },
};
globalThis.document = { addEventListener() {} };
globalThis.location = { hash: '' };
globalThis.localStorage = {
  getItem(key) { return localStorageState.has(key) ? localStorageState.get(key) : null; },
  setItem(key, value) { localStorageState.set(key, String(value)); },
  removeItem(key) { localStorageState.delete(key); },
};

const { app } = await import('./app.js');

const cardsSeed = [{ id: 'c-seed', title: 'Seed Card', topics: ['basics'] }];
const quizzesSeed = [{ id: 'q-seed', cardId: 'c-seed' }];
const glossarySeed = { ETF: '指数基金的一种' };
const articlesSeed = [{ id: 'a-seed', title: 'Seed Article', topics: ['basics'] }];

const originalFetch = globalThis.fetch;

function makeJsonResponse(data) {
  return {
    ok: true,
    status: 200,
    json: async () => data,
  };
}

async function testRepositoryUsesApiDataWhenAvailable() {
  let calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    if (url === './data/knowledge-cards.json') return makeJsonResponse(cardsSeed);
    if (url === '/api/content?type=knowledge_card') return makeJsonResponse([{ id: 'c-api', title: 'API Card' }]);
    throw new Error(`unexpected url: ${url}`);
  };

  const cards = await repository.getContentByType('knowledge_card');
  assert.deepEqual(cards, [{ id: 'c-api', title: 'API Card' }]);
  assert.deepEqual(calls, ['/api/content?type=knowledge_card']);
}

async function testRepositoryFallsBackToSeedData() {
  let calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    if (url === './data/knowledge-cards.json') return makeJsonResponse(cardsSeed);
    throw Object.assign(new Error('network down'), { code: 'FETCH_FAILED' });
  };

  const cards = await repository.getContentByType('knowledge_card');
  assert.deepEqual(cards, cardsSeed);
  assert.deepEqual(calls, ['/api/content?type=knowledge_card', './data/knowledge-cards.json']);
}

async function testRepositoryLoadsEachSeedType() {
  globalThis.fetch = async (url) => {
    if (url === './data/knowledge-cards.json') return makeJsonResponse(cardsSeed);
    if (url === './data/quiz.json') return makeJsonResponse(quizzesSeed);
    if (url === './data/glossary.json') return makeJsonResponse(glossarySeed);
    if (url === './data/articles.json') return makeJsonResponse(articlesSeed);
    throw new Error(`unexpected url: ${url}`);
  };

  assert.deepEqual(await repository.loadSeedData('knowledge_card'), cardsSeed);
  assert.deepEqual(await repository.loadSeedData('quiz'), quizzesSeed);
  assert.deepEqual(await repository.loadSeedData('glossary'), glossarySeed);
  assert.deepEqual(await repository.loadSeedData('article'), articlesSeed);
}

async function testRefreshMeLoadsRecommendationsForAuthedUser() {
  globalThis.fetch = async (url) => {
    if (url === '/api/recommendations?num=3') {
      return makeJsonResponse({ recommendations: [
        { id: 'rec-1', type: 'knowledge_card', data: { id: 'c101', title: '推荐卡1', body: '<p>1</p>', difficulty: 'L1', topics: ['basics'], quizIds: [] } },
        { id: 'rec-2', type: 'knowledge_card', data: { id: 'c102', title: '推荐卡2', body: '<p>2</p>', difficulty: 'L1', topics: ['fund'], quizIds: [] } },
        { id: 'rec-3', type: 'knowledge_card', data: { id: 'c103', title: '推荐卡3', body: '<p>3</p>', difficulty: 'L2', topics: ['stock'], quizIds: [] } },
        { id: 'rec-4', type: 'knowledge_card', data: { id: 'c104', title: '推荐卡4', body: '<p>4</p>', difficulty: 'L2', topics: ['insurance'], quizIds: [] } },
      ] });
    }
    throw new Error(`unexpected url: ${url}`);
  };

  const vm = app();
  vm.authUser = 'tester';
  vm.cards = cardsSeed;
  vm.quiz = quizzesSeed;
  vm.glossary = glossarySeed;
  await vm.loadRecommendations();

  assert.equal(vm.personalizedRecommendations.length, 3);
  assert.equal(vm.personalizedRecommendations[0].id, 'c101');
  assert.equal(vm.personalizedRecommendations[2].id, 'c103');
}

async function testRefreshMeSkipsRecommendationsWhenLoggedOut() {
  let called = false;
  globalThis.fetch = async () => {
    called = true;
    throw new Error('should not request');
  };

  const vm = app();
  vm.authUser = null;
  vm.cards = cardsSeed;
  vm.quiz = quizzesSeed;
  vm.glossary = glossarySeed;
  vm.refreshMe();
  await Promise.resolve();

  assert.deepEqual(vm.personalizedRecommendations, []);
  assert.equal(called, false);
}

async function testOpenRecommendationShowsCardOnHome() {
  const vm = app();
  const recommendation = { id: 'c201', title: '推荐直达卡', body: '<p>x</p>', difficulty: 'L1', topics: ['basics'], quizIds: [] };
  globalThis.location = { hash: '' };

  vm.openRecommendation(recommendation);

  assert.equal(vm.todayCard, recommendation);
  assert.equal(vm.route, 'home');
  assert.equal(globalThis.location.hash, '#/home');
}

try {
  await testRepositoryUsesApiDataWhenAvailable();
  await testRepositoryFallsBackToSeedData();
  await testRepositoryLoadsEachSeedType();
  await testRefreshMeLoadsRecommendationsForAuthedUser();
  await testRefreshMeSkipsRecommendationsWhenLoggedOut();
  await testOpenRecommendationShowsCardOnHome();
  console.log('repository-app.test.mjs OK');
} finally {
  globalThis.fetch = originalFetch;
}

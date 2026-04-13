import { createRouter, createWebHistory } from 'vue-router'
import ClipsView from './views/ClipsView.vue'
import ResultsView from './views/ResultsView.vue'
import AIOptimizationView from './views/AIOptimizationView.vue'

const routes = [
  { path: '/', redirect: '/clips' },
  { path: '/clips', name: 'clips', component: ClipsView },
  { path: '/results', name: 'results', component: ResultsView },
  { path: '/ai-optimization', name: 'ai-optimization', component: AIOptimizationView },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})

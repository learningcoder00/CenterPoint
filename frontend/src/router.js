import { createRouter, createWebHistory } from 'vue-router'
import HomeView from './views/HomeView.vue'
import ClipsView from './views/ClipsView.vue'
import ResultsView from './views/ResultsView.vue'
import AIOptimizationView from './views/AIOptimizationView.vue'
import ReviewView from './views/ReviewView.vue'
import CompareResultsView from './views/CompareResultsView.vue'

const routes = [
  { path: '/', redirect: '/home' },
  { path: '/home', name: 'home', component: HomeView },
  { path: '/clips', name: 'clips', component: ClipsView },
  { path: '/results', name: 'results', component: ResultsView },
  { path: '/compare', name: 'compare', component: CompareResultsView },
  { path: '/review', name: 'review', component: ReviewView },
  { path: '/ai-optimization', name: 'ai-optimization', component: AIOptimizationView },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})

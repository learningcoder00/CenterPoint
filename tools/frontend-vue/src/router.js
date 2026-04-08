import { createRouter, createWebHistory } from 'vue-router'
import ClipsView from './views/ClipsView.vue'
import ResultsView from './views/ResultsView.vue'

const routes = [
  { path: '/', redirect: '/clips' },
  { path: '/clips', name: 'clips', component: ClipsView },
  { path: '/results', name: 'results', component: ResultsView },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})

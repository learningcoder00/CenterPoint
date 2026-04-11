<template>
  <section class="hero">
    <div>
      <h1>AI 优化建议</h1>
      <p>提交作业 ID 和问题描述，获取 AI 生成的优化建议。</p>
    </div>
  </section>

  <section class="controls">
    <div class="search-box">
      <span>Filter</span>
      <input v-model="search" type="text" placeholder="Search by job id">
    </div>
    <button class="btn-refresh" @click="loadOptimizations">刷新</button>
  </section>

  <div class="container">
    <div class="card">
      <h2>提交优化请求</h2>
      
      <div class="form-group">
        <label for="jobId">作业 ID</label>
        <input type="text" id="jobId" v-model="form.jobId" placeholder="输入作业 ID">
      </div>
      
      <div class="form-group">
        <label for="description">问题描述</label>
        <textarea id="description" v-model="form.description" placeholder="描述检测结果的不足或问题"></textarea>
      </div>
      
      <button class="btn" @click="submitRequest" :disabled="isSubmitting">
        {{ isSubmitting ? '提交中...' : '提交请求' }}
      </button>
    </div>
    
    <div v-if="response" class="card">
      <h2>AI 优化建议</h2>
      <div class="response">
        {{ response }}
      </div>
    </div>
  </div>

  <div v-if="loadingOptimizations" class="loading">Loading optimizations…</div>
  <div v-else-if="!filteredOptimizations.length" class="empty">
    还没有优化建议。提交一个请求来获取 AI 生成的优化建议。
  </div>
  <div v-else class="grid">
    <div v-for="opt in filteredOptimizations" :key="opt.id" class="optimization-card">
      <div class="optimization-header">
        <span class="job-id">Job ID: {{ opt.jobId }}</span>
        <div class="header-right">
          <span class="created-at">{{ formatDate(opt.createdAt) }}</span>
          <button class="delete-btn" @click="deleteOptimization(opt.id)">删除</button>
        </div>
      </div>
      <div class="optimization-description">
        <strong>问题描述:</strong> {{ opt.description || '无' }}
      </div>
      <div class="optimization-response">
        <strong>优化建议:</strong>
        <pre>{{ opt.response }}</pre>
      </div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'AIOptimizationView',
  data() {
    return {
      form: {
        jobId: '',
        description: ''
      },
      isSubmitting: false,
      response: null,
      allOptimizations: [],
      loadingOptimizations: false,
      search: ''
    }
  },
  computed: {
    filteredOptimizations() {
      let result = [...this.allOptimizations];
      const q = this.search.trim().toLowerCase();
      if (q) result = result.filter(opt => opt.jobId.includes(q));
      return result;
    }
  },
  mounted() {
    // 从URL查询参数中获取jobId
    const urlParams = new URLSearchParams(window.location.search);
    const jobId = urlParams.get('jobId');
    if (jobId) {
      this.form.jobId = jobId;
    }
    
    // 加载优化建议列表
    this.loadOptimizations();
  },
  methods: {
    async submitRequest() {
      if (!this.form.jobId) {
        alert('请输入作业 ID');
        return;
      }
      
      this.isSubmitting = true;
      this.response = null;
      
      try {
        const response = await fetch('/api/ai/optimization', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json; charset=utf-8'
          },
          body: JSON.stringify(this.form)
        });
        
        if (!response.ok) {
          throw new Error('请求失败');
        }
        
        const data = await response.json();
        this.response = data.response;
        
        // 重新加载优化建议列表
        this.loadOptimizations();
      } catch (error) {
        console.error('请求失败:', error);
        alert('请求失败，请稍后重试');
      } finally {
        this.isSubmitting = false;
      }
    },
    async loadOptimizations() {
      this.loadingOptimizations = true;
      
      try {
        const response = await fetch('/api/ai/optimizations');
        
        if (!response.ok) {
          throw new Error('请求失败');
        }
        
        const data = await response.json();
        this.allOptimizations = data.optimizations || [];
      } catch (error) {
        console.error('加载优化建议失败:', error);
      } finally {
        this.loadingOptimizations = false;
      }
    },
    formatDate(timestamp) {
      const date = new Date(timestamp * 1000);
      return date.toLocaleString();
    },
    async deleteOptimization(id) {
      if (!confirm('确定要删除这条优化建议吗？')) {
        return;
      }
      
      try {
        const response = await fetch(`/api/ai/optimizations/${id}`, {
          method: 'DELETE'
        });
        
        if (!response.ok) {
          throw new Error('删除失败');
        }
        
        const data = await response.json();
        if (data.success) {
          // 重新加载优化建议列表
          this.loadOptimizations();
        }
      } catch (error) {
        console.error('删除失败:', error);
        alert('删除失败，请稍后重试');
      }
    }
  }
}
</script>

<style scoped>
.container {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

.card {
  background: rgba(10, 13, 22, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
  backdrop-filter: blur(10px);
}

.form-group {
  margin-bottom: 15px;
}

label {
  display: block;
  margin-bottom: 5px;
  font-weight: 500;
  color: var(--text);
}

input, textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid var(--border);
  border-radius: 8px;
  font-size: 16px;
  background: rgba(255, 255, 255, 0.05);
  color: var(--text);
}

input:focus, textarea:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 2px rgba(147, 197, 253, 0.2);
}

textarea {
  height: 150px;
  resize: vertical;
}

.btn {
  background: var(--accent);
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 16px;
  transition: background 0.3s;
}

.btn:hover {
  background: #0069d9;
}

.btn:disabled {
  background: var(--muted);
  cursor: not-allowed;
}

.response {
  margin-top: 10px;
  padding: 15px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  white-space: pre-wrap;
  color: var(--text);
}

/* 优化建议卡片样式 */
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(400px, 1fr));
  gap: 16px;
  padding: 0 20px;
  max-width: 1200px;
  margin: 0 auto 40px;
}

.optimization-card {
  background: rgba(10, 13, 22, 0.8);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 16px;
  backdrop-filter: blur(10px);
  transition: transform 0.2s, box-shadow 0.2s;
}

.optimization-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.optimization-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.delete-btn {
  padding: 4px 8px;
  border: 1px solid rgba(255, 0, 0, 0.5);
  border-radius: 4px;
  background: rgba(255, 0, 0, 0.1);
  color: #ff6b6b;
  font-size: 11px;
  cursor: pointer;
  transition: all 0.3s;
}

.delete-btn:hover {
  background: rgba(255, 0, 0, 0.2);
  border-color: rgba(255, 0, 0, 0.8);
}

.job-id {
  font-size: 13px;
  color: var(--text);
  font-weight: 500;
}

.created-at {
  font-size: 11px;
  color: var(--muted);
}

.optimization-description {
  margin-bottom: 12px;
  font-size: 14px;
  color: var(--text);
  line-height: 1.4;
}

.optimization-response {
  font-size: 13px;
  color: var(--text);
  line-height: 1.4;
}

.optimization-response pre {
  margin-top: 8px;
  padding: 12px;
  background: rgba(255, 255, 255, 0.05);
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 8px;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: inherit;
}

/* 加载和空状态样式 */
.loading, .empty {
  text-align: center;
  padding: 60px 20px;
  color: var(--muted);
}

/* 搜索和刷新按钮样式 */
.controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 20px 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.search-box {
  display: flex;
  align-items: center;
  gap: 10px;
}

.search-box input {
  width: 300px;
  padding: 8px 12px;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.05);
  color: var(--text);
  font-size: 13px;
}

.btn-refresh {
  padding: 10px 16px;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: transparent;
  color: var(--text);
  font-size: 13px;
  cursor: pointer;
  white-space: nowrap;
}

.btn-refresh:hover {
  background: rgba(255, 255, 255, 0.08);
}
</style>
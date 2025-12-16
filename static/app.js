// PR 코멘트 로딩 상태 관리
const loadedPRs = new Set();
const expandedPRs = new Set();

/**
 * PR 토글 (펼치기/접기)
 */
function togglePR(prNumber) {
  const commentsDiv = document.getElementById(`pr-comments-${prNumber}`);
  const prDiv = document.querySelector(`[data-pr-number="${prNumber}"]`);
  const toggle = prDiv.querySelector('.pr-toggle');
  
  if (expandedPRs.has(prNumber)) {
    // 접기
    commentsDiv.style.display = 'none';
    toggle.textContent = '▶';
    expandedPRs.delete(prNumber);
  } else {
    // 펼치기
    commentsDiv.style.display = 'block';
    toggle.textContent = '▼';
    expandedPRs.add(prNumber);
    
    // 아직 로드되지 않았다면 로드
    if (!loadedPRs.has(prNumber)) {
      loadPRComments(prNumber);
    }
  }
}

/**
 * PR 코멘트 로드
 */
async function loadPRComments(prNumber) {
  const commentsDiv = document.getElementById(`pr-comments-${prNumber}`);
  const includeResolved = document.getElementById('include_resolved').checked;
  
  try {
    const response = await fetch(`/api/pr/${prNumber}/comments?include_resolved=${includeResolved}`);
    const result = await response.json();
    
    if (!response.ok) {
      throw new Error(result.error || '코멘트를 불러오지 못했습니다.');
    }
    
    const data = result.data;
    
    if (!data.comments || data.comments.length === 0) {
      commentsDiv.innerHTML = `
        <div class="no-comments-inline">
          <p>리뷰 코멘트가 없습니다.</p>
        </div>
      `;
    } else {
      commentsDiv.innerHTML = renderComments(data.comments);
    }
    
    loadedPRs.add(prNumber);
  } catch (error) {
    commentsDiv.innerHTML = `
      <div class="error-inline">
        <p>❌ ${error.message}</p>
        <button onclick="loadPRComments(${prNumber})">다시 시도</button>
      </div>
    `;
  }
}

/**
 * 코멘트 렌더링
 */
function renderComments(comments) {
  return comments.map(comment => {
    const resolvedClass = comment.isResolved ? 'resolved' : '';
    const resolvedBadge = comment.isResolved ? '<span class="resolved-badge">✓ 해결됨</span>' : '';
    
    return `
      <div class="comment ${resolvedClass}">
        <div class="comment-header">
          <div class="comment-author">
            ${comment.authorUrl 
              ? `<a href="${comment.authorUrl}" target="_blank" rel="noopener noreferrer">@${comment.author}</a>`
              : `@${comment.author}`
            }
            ${resolvedBadge}
          </div>
          <div class="comment-link">
            ${comment.url 
              ? `<a href="${comment.url}" target="_blank" rel="noopener noreferrer">GitHub에서 보기 →</a>`
              : ''
            }
          </div>
        </div>
        
        ${comment.path ? `
          <div class="comment-path">
            📄 ${comment.path}
            ${comment.lineInfo ? `<span class="line-info">${comment.lineInfo}</span>` : ''}
          </div>
        ` : ''}
        
        ${comment.diffHunk ? `
          <pre class="diff"><code>${formatDiff(comment.diffHunk)}</code></pre>
        ` : ''}
        
        <div class="comment-body">
          ${comment.bodyHTML}
        </div>
      </div>
    `;
  }).join('');
}

/**
 * Diff 포매팅 (초록/빨강 색상)
 */
function formatDiff(diffHunk) {
  if (!diffHunk) return '';
  
  const lines = diffHunk.split('\n');
  return lines.map(line => {
    const escaped = escapeHtml(line);
    
    if (line.startsWith('@@')) {
      return `<span class="diff-hunk-header">${escaped}</span>`;
    } else if (line.startsWith('+') && !line.startsWith('+++')) {
      return `<span class="diff-addition">${escaped}</span>`;
    } else if (line.startsWith('-') && !line.startsWith('---')) {
      return `<span class="diff-deletion">${escaped}</span>`;
    } else if (line.startsWith('+++') || line.startsWith('---')) {
      return `<span class="diff-file">${escaped}</span>`;
    } else {
      return `<span class="diff-context">${escaped}</span>`;
    }
  }).join('\n');
}

/**
 * HTML 이스케이프
 */
function escapeHtml(text) {
  const map = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  return text.replace(/[&<>"']/g, m => map[m]);
}

/**
 * "해결된 코멘트 포함" 체크박스 변경 시
 */
document.getElementById('include_resolved').addEventListener('change', function() {
  // 이미 펼쳐진 PR들을 다시 로드
  expandedPRs.forEach(prNumber => {
    loadedPRs.delete(prNumber);
    loadPRComments(prNumber);
  });
});

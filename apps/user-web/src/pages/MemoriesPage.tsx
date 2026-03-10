/* ============================================================
 * 记忆页 - 搜索 + 分类导航 + 列表 + 详情抽屉
 * ============================================================ */
import { useState } from 'react';
import { useI18n, type MessageKey } from '../i18n';
import { PageHeader, Card, EmptyState } from '../components/base';

type MemoryType = 'all' | 'fact' | 'event' | 'preference' | 'relation';

interface MemoryItem {
  id: string;
  type: MemoryType;
  title: string;
  content: string;
  source: string;
  visibility: string;
  status: string;
  updatedAt: string;
}

const MOCK_MEMORIES: MemoryItem[] = [
  { id: '1', type: 'preference', title: '奶奶的饮食偏好', content: '奶奶喜欢清淡口味，不吃辛辣食物，每天晚餐前需要服药', source: '对话记录', visibility: '全家可见', status: '有效', updatedAt: '2 天前' },
  { id: '2', type: 'fact', title: '小明的学校信息', content: '小明在阳光小学读三年级，每周三有课外活动', source: '手动录入', visibility: '全家可见', status: '有效', updatedAt: '1 周前' },
  { id: '3', type: 'event', title: '上次家庭聚餐', content: '上周六全家在客厅吃了火锅，奶奶很开心', source: '对话记录', visibility: '全家可见', status: '有效', updatedAt: '3 天前' },
  { id: '4', type: 'relation', title: '阿姨的联系方式', content: '张阿姨电话 138xxxx，是奶奶的老朋友，周末经常来串门', source: '对话记录', visibility: '管理员可见', status: '待确认', updatedAt: '5 天前' },
  { id: '5', type: 'preference', title: '爸爸的温度偏好', content: '爸爸喜欢室温 24°C，睡觉时调到 22°C', source: '智能学习', visibility: '全家可见', status: '有效', updatedAt: '1 天前' },
];

const typeMap: Record<string, { labelKey: MessageKey; icon: string }> = {
  all: { labelKey: 'memory.all', icon: '📋' },
  fact: { labelKey: 'memory.facts', icon: '📌' },
  event: { labelKey: 'memory.events', icon: '📅' },
  preference: { labelKey: 'memory.preferences', icon: '💡' },
  relation: { labelKey: 'memory.relations', icon: '🔗' },
};

export function MemoriesPage() {
  const { t } = useI18n();
  const [activeType, setActiveType] = useState<MemoryType>('all');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const filtered = MOCK_MEMORIES.filter(m =>
    (activeType === 'all' || m.type === activeType) &&
    (searchQuery === '' || m.title.includes(searchQuery) || m.content.includes(searchQuery))
  );

  const selectedMemory = MOCK_MEMORIES.find(m => m.id === selectedId);

  return (
    <div className="page page--memories">
      <PageHeader title={t('nav.memories')} />

      {/* 搜索区 */}
      <div className="memory-search">
        <input
          type="text"
          placeholder={t('memory.search')}
          value={searchQuery}
          onChange={e => setSearchQuery(e.target.value)}
          className="search-input search-input--lg"
        />
      </div>

      <div className="memory-layout">
        {/* 分类导航 */}
        <nav className="memory-categories">
          {(Object.keys(typeMap) as MemoryType[]).map(type => (
            <button
              key={type}
              className={`memory-cat-btn ${activeType === type ? 'memory-cat-btn--active' : ''}`}
              onClick={() => setActiveType(type)}
            >
              <span>{typeMap[type].icon}</span>
              <span>{t(typeMap[type].labelKey)}</span>
            </button>
          ))}
        </nav>

        {/* 列表区 */}
        <div className="memory-list">
          {filtered.length > 0 ? filtered.map(m => (
            <Card
              key={m.id}
              className={`memory-item-card ${selectedId === m.id ? 'memory-item-card--selected' : ''}`}
              onClick={() => setSelectedId(m.id)}
            >
              <div className="memory-item-card__top">
                <span className="memory-item-card__icon">{typeMap[m.type]?.icon}</span>
                <h3 className="memory-item-card__title">{m.title}</h3>
                <span className={`badge badge--${m.status === '有效' ? 'success' : 'warning'}`}>{m.status}</span>
              </div>
              <p className="memory-item-card__content">{m.content}</p>
              <div className="memory-item-card__meta">
                <span>{t('memory.source')}：{m.source}</span>
                <span>{t('memory.updatedAt')}：{m.updatedAt}</span>
              </div>
            </Card>
          )) : (
            <EmptyState icon="📝" title={t('memory.noResults')} description={t('memory.noResultsHint')} />
          )}
        </div>

        {/* 详情抽屉 */}
        <div className={`memory-detail ${selectedMemory ? 'memory-detail--open' : ''}`}>
          {selectedMemory ? (
            <>
              <div className="memory-detail__header">
                <h2>{t('memory.detail')}</h2>
                <button className="close-btn" onClick={() => setSelectedId(null)}>✕</button>
              </div>
              <div className="memory-detail__body">
                <div className="detail-field">
                  <label>内容</label>
                  <p>{selectedMemory.content}</p>
                </div>
                <div className="detail-field">
                  <label>{t('memory.source')}</label>
                  <p>{selectedMemory.source}</p>
                </div>
                <div className="detail-field">
                  <label>{t('memory.visibility')}</label>
                  <p>{selectedMemory.visibility}</p>
                </div>
                <div className="detail-field">
                  <label>{t('memory.status')}</label>
                  <p>{selectedMemory.status}</p>
                </div>
                <div className="detail-field">
                  <label>{t('memory.updatedAt')}</label>
                  <p>{selectedMemory.updatedAt}</p>
                </div>
              </div>
              <div className="memory-detail__actions">
                <button className="btn btn--outline">{t('memory.edit')}</button>
                <button className="btn btn--outline">{t('memory.correct')}</button>
                <button className="btn btn--outline btn--warning">{t('memory.invalidate')}</button>
                <button className="btn btn--outline btn--danger">{t('memory.delete')}</button>
              </div>
            </>
          ) : (
            <div className="memory-detail__empty">
              <p>点击左侧记忆条目查看详情</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

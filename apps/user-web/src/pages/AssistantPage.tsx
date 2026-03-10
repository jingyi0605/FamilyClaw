/* ============================================================
 * 助手页 - 三栏布局：会话列表 + 对话区 + 上下文侧栏
 * ============================================================ */
import { useState } from 'react';
import { useI18n } from '../i18n';
import { useHouseholdContext } from '../state/household';
import { EmptyState } from '../components/base';

interface Session {
  id: string;
  title: string;
  lastMessage: string;
  time: string;
  pinned: boolean;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  usedMemory?: boolean;
}

const MOCK_SESSIONS: Session[] = [
  { id: '1', title: '晚餐建议', lastMessage: '今天可以试试清蒸鱼...', time: '10 分钟前', pinned: true },
  { id: '2', title: '奶奶用药提醒', lastMessage: '已帮您设置每天 8:00 的提醒', time: '1 小时前', pinned: false },
  { id: '3', title: '周末活动规划', lastMessage: '推荐去附近的公园散步...', time: '昨天', pinned: false },
];

const MOCK_MESSAGES: Message[] = [
  { id: '1', role: 'user', content: '今天晚上吃什么比较好？家里有鱼和蔬菜。' },
  { id: '2', role: 'assistant', content: '根据你家的食材和奶奶的饮食偏好，我建议今天做清蒸鱼配时令蔬菜。清蒸鱼既营养又容易消化，适合全家人。需要我帮你找一个详细的食谱吗？', usedMemory: true },
  { id: '3', role: 'user', content: '好的，顺便提醒一下明天的菜单也帮我想想。' },
  { id: '4', role: 'assistant', content: '好的！明天可以考虑做番茄鸡蛋面，简单快手，小明也喜欢吃。我帮你设一个明天早上的菜单提醒好吗？' },
];

export function AssistantPage() {
  const { t } = useI18n();
  const { currentHousehold } = useHouseholdContext();
  const [activeSession, setActiveSession] = useState<string>('1');
  const [inputValue, setInputValue] = useState('');

  return (
    <div className="page page--assistant">
      {/* 左栏：会话列表 */}
      <div className="assistant-sidebar">
        <div className="assistant-sidebar__header">
          <h2>{t('nav.assistant')}</h2>
          <button className="btn btn--primary btn--sm">{t('assistant.newChat')}</button>
        </div>
        <div className="assistant-sidebar__search">
          <input type="text" placeholder={t('assistant.search')} className="search-input" />
        </div>
        <div className="assistant-sidebar__list">
          {MOCK_SESSIONS.map(session => (
            <div
              key={session.id}
              className={`session-item ${activeSession === session.id ? 'session-item--active' : ''}`}
              onClick={() => setActiveSession(session.id)}
            >
              {session.pinned && <span className="session-item__pin">📌</span>}
              <div className="session-item__content">
                <span className="session-item__title">{session.title}</span>
                <span className="session-item__preview">{session.lastMessage}</span>
              </div>
              <span className="session-item__time">{session.time}</span>
            </div>
          ))}
        </div>
      </div>

      {/* 中栏：对话区 */}
      <div className="assistant-main">
        {activeSession ? (
          <>
            <div className="assistant-main__messages">
              {MOCK_MESSAGES.map(msg => (
                <div key={msg.id} className={`message message--${msg.role}`}>
                  <div className="message__bubble">
                    <p className="message__content">{msg.content}</p>
                    {msg.usedMemory && (
                      <span className="message__memory-tag">📝 引用了家庭记忆</span>
                    )}
                  </div>
                  {msg.role === 'assistant' && (
                    <div className="message__actions">
                      <button className="msg-action-btn">{t('assistant.askFollow')}</button>
                      <button className="msg-action-btn">{t('assistant.toReminder')}</button>
                      <button className="msg-action-btn">{t('assistant.toMemory')}</button>
                    </div>
                  )}
                </div>
              ))}
            </div>
            <div className="assistant-main__input">
              <input
                type="text"
                value={inputValue}
                onChange={e => setInputValue(e.target.value)}
                placeholder={t('assistant.inputPlaceholder')}
                className="chat-input"
              />
              <button className="btn btn--primary">{t('assistant.send')}</button>
            </div>
          </>
        ) : (
          <EmptyState
            icon="💬"
            title={t('assistant.noSessions')}
            description={t('assistant.noSessionsHint')}
          />
        )}
      </div>

      {/* 右栏：上下文侧栏 */}
      <div className="assistant-context">
        <div className="context-section">
          <h3 className="context-section__title">{t('assistant.context')}</h3>
          <div className="context-item">
            <span className="context-item__label">{t('assistant.currentFamily')}</span>
            <span className="context-item__value">{currentHousehold?.name ?? '-'}</span>
          </div>
        </div>

        <div className="context-section">
          <h3 className="context-section__title">{t('assistant.recentMemories')}</h3>
          <div className="context-memory-list">
            <div className="context-memory-item">
              <span>🐟</span> 奶奶喜欢清淡饮食
            </div>
            <div className="context-memory-item">
              <span>🍝</span> 小明爱吃面条
            </div>
            <div className="context-memory-item">
              <span>🥦</span> 妈妈最近在控制饮食
            </div>
          </div>
        </div>

        <div className="context-section">
          <h3 className="context-section__title">{t('assistant.quickActions')}</h3>
          <div className="context-actions">
            <button className="context-action-btn">🔔 创建提醒</button>
            <button className="context-action-btn">📝 写入记忆</button>
            <button className="context-action-btn">🎬 触发场景</button>
          </div>
        </div>
      </div>
    </div>
  );
}

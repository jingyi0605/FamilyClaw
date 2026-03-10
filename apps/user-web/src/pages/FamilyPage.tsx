/* ============================================================
 * 家庭页 - 包含概览/房间/成员/关系四个子路由
 * ============================================================ */
import { NavLink, Outlet, useMatch } from 'react-router-dom';
import { useI18n } from '../i18n';
import { PageHeader, Card, Section, EmptyState } from '../components/base';
import { useHouseholdContext } from '../state/household';

/* ---- 家庭子导航 ---- */
const familyTabs = [
  { to: '/family', labelKey: 'family.overview' as const, end: true },
  { to: '/family/rooms', labelKey: 'family.rooms' as const },
  { to: '/family/members', labelKey: 'family.members' as const },
  { to: '/family/relationships', labelKey: 'family.relationships' as const },
];

export function FamilyLayout() {
  const { t } = useI18n();

  return (
    <div className="page page--family">
      <PageHeader title={t('nav.family')} />
      <nav className="family-tabs">
        {familyTabs.map(tab => (
          <NavLink
            key={tab.to}
            to={tab.to}
            end={tab.end}
            className={({ isActive }) => `family-tab ${isActive ? 'family-tab--active' : ''}`}
          >
            {t(tab.labelKey)}
          </NavLink>
        ))}
      </nav>
      <div className="family-content">
        <Outlet />
      </div>
    </div>
  );
}

/* ---- 家庭概览 ---- */
export function FamilyOverview() {
  const { t } = useI18n();
  const { currentHousehold } = useHouseholdContext();

  return (
    <div className="family-overview">
      <div className="overview-grid">
        <Card className="overview-card">
          <div className="overview-card__label">{t('family.name')}</div>
          <div className="overview-card__value">{currentHousehold?.name ?? '-'}</div>
        </Card>
        <Card className="overview-card">
          <div className="overview-card__label">{t('family.timezone')}</div>
          <div className="overview-card__value">Asia/Shanghai (UTC+8)</div>
        </Card>
        <Card className="overview-card">
          <div className="overview-card__label">{t('family.language')}</div>
          <div className="overview-card__value">中文</div>
        </Card>
        <Card className="overview-card">
          <div className="overview-card__label">{t('family.mode')}</div>
          <div className="overview-card__value">日常模式</div>
        </Card>
        <Card className="overview-card">
          <div className="overview-card__label">{t('family.privacy')}</div>
          <div className="overview-card__value">标准</div>
        </Card>
        <Card className="overview-card">
          <div className="overview-card__label">{t('family.services')}</div>
          <div className="overview-card__value">问答 · 提醒 · 场景</div>
        </Card>
      </div>
    </div>
  );
}

/* ---- 房间页 ---- */
const MOCK_ROOMS = [
  { id: '1', name: '客厅', type: '生活区', devices: 5, active: true, sensitive: false },
  { id: '2', name: '主卧', type: '卧室', devices: 3, active: false, sensitive: true },
  { id: '3', name: '厨房', type: '功能区', devices: 4, active: true, sensitive: false },
  { id: '4', name: '书房', type: '工作区', devices: 2, active: false, sensitive: false },
  { id: '5', name: '卫生间', type: '功能区', devices: 1, active: false, sensitive: true },
];

export function FamilyRooms() {
  const { t } = useI18n();

  return (
    <div className="family-rooms">
      <div className="room-grid">
        {MOCK_ROOMS.map(room => (
          <Card key={room.id} className="room-detail-card">
            <div className="room-detail-card__top">
              <h3 className="room-detail-card__name">{room.name}</h3>
              {room.sensitive && <span className="badge badge--warning">{t('room.sensitive')}</span>}
            </div>
            <div className="room-detail-card__meta">
              <span className="meta-item">📦 {room.type}</span>
              <span className="meta-item">📱 {room.devices} {t('room.devices')}</span>
              <span className={`meta-item ${room.active ? 'meta-item--active' : ''}`}>
                {room.active ? `🟢 ${t('room.active')}` : `⚪ ${t('room.idle')}`}
              </span>
            </div>
            <button className="card-action-btn">{t('common.edit')}</button>
          </Card>
        ))}
      </div>
    </div>
  );
}

/* ---- 成员页 ---- */
const MOCK_MEMBERS = [
  { id: '1', name: '爸爸', avatar: '👨', role: '管理员', status: 'home', prefs: '温度偏好 24°C · 通知偏好 全部开启' },
  { id: '2', name: '妈妈', avatar: '👩', role: '成员', status: 'home', prefs: '温度偏好 23°C · 免打扰 22:00-7:00' },
  { id: '3', name: '小明', avatar: '👦', role: '成员', status: 'away', prefs: '关注区域 书房 · 通知偏好 仅紧急' },
  { id: '4', name: '奶奶', avatar: '👵', role: '成员', status: 'home', prefs: '长辈模式已开启 · 提醒偏好 语音+文字' },
];

export function FamilyMembers() {
  const { t } = useI18n();

  return (
    <div className="family-members">
      <div className="member-detail-grid">
        {MOCK_MEMBERS.map(m => (
          <Card key={m.id} className="member-detail-card">
            <div className="member-detail-card__top">
              <div className="member-detail-card__avatar">{m.avatar}</div>
              <div className="member-detail-card__info">
                <h3 className="member-detail-card__name">{m.name}</h3>
                <span className="member-detail-card__role">{m.role}</span>
              </div>
              <span className={`badge badge--${m.status === 'home' ? 'success' : 'secondary'}`}>
                {m.status === 'home' ? t('member.atHome') : t('member.away')}
              </span>
            </div>
            <p className="member-detail-card__prefs">{m.prefs}</p>
            <div className="member-detail-card__actions">
              <button className="card-action-btn">{t('member.edit')}</button>
              <button className="card-action-btn">{t('member.preferences')}</button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

/* ---- 关系页 ---- */
const MOCK_RELATIONS = [
  { id: '1', from: '👨 爸爸', to: '👵 奶奶', type: '照护关系', desc: '爸爸是奶奶的主要照护人' },
  { id: '2', from: '👨 爸爸', to: '👦 小明', type: '监护关系', desc: '爸爸是小明的法定监护人' },
  { id: '3', from: '👩 妈妈', to: '👦 小明', type: '监护关系', desc: '妈妈是小明的法定监护人' },
  { id: '4', from: '👩 妈妈', to: '👵 奶奶', type: '照护关系', desc: '妈妈协助照护奶奶' },
];

export function FamilyRelationships() {
  const { t } = useI18n();

  return (
    <div className="family-relationships">
      {/* 关系图谱占位 */}
      <Card className="relationship-graph-placeholder">
        <div className="relationship-graph__hint">
          <span className="relationship-graph__icon">🔗</span>
          <p>家庭关系图谱（后续实现可视化）</p>
        </div>
      </Card>

      <Section title={t('relationship.caregiving')}>
        <div className="relation-list">
          {MOCK_RELATIONS.filter(r => r.type === '照护关系').map(r => (
            <Card key={r.id} className="relation-card">
              <div className="relation-card__pair">
                <span>{r.from}</span>
                <span className="relation-card__arrow">→</span>
                <span>{r.to}</span>
              </div>
              <p className="relation-card__desc">{r.desc}</p>
            </Card>
          ))}
        </div>
      </Section>

      <Section title={t('relationship.guardianship')}>
        <div className="relation-list">
          {MOCK_RELATIONS.filter(r => r.type === '监护关系').map(r => (
            <Card key={r.id} className="relation-card">
              <div className="relation-card__pair">
                <span>{r.from}</span>
                <span className="relation-card__arrow">→</span>
                <span>{r.to}</span>
              </div>
              <p className="relation-card__desc">{r.desc}</p>
            </Card>
          ))}
        </div>
      </Section>
    </div>
  );
}

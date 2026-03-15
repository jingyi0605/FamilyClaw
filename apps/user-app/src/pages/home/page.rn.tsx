import type { ReactNode } from 'react';
import { Text, View } from '@tarojs/components';
import {
  COPY,
  formatAutomationLevel,
  formatHomeAssistantStatus,
  formatMode,
  formatPrivacyMode,
  getMemberCards,
  getRoomCards,
  useHomeDashboardData,
} from './page.shared';
import './index.rn.scss';

function SectionCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <View className="home-rn-card">
      <Text className="home-rn-card__title">{title}</Text>
      {children}
    </View>
  );
}

export default function HomePage() {
  const { familyName, dashboardData, loading } = useHomeDashboardData();
  const roomCards = getRoomCards(dashboardData).slice(0, 4);
  const memberCards = getMemberCards(dashboardData).slice(0, 4);
  const recentEvents = [
    ...(dashboardData.overview?.insights.slice(0, 3).map(item => item.message) ?? []),
    ...(dashboardData.reminders?.items.slice(0, 3).map(item => item.latest_ack_action === 'done' ? `${item.title} 已完成` : `${item.title} 待处理`) ?? []),
  ].slice(0, 5);

  return (
    <View className="home-rn-page">
      <View className="home-rn-banner">
        <Text className="home-rn-banner__title">{COPY['home.welcome']}，{familyName}</Text>
        <Text className="home-rn-banner__sub">{COPY['home.greeting']}</Text>
        {dashboardData.errors.length > 0 && <Text className="home-rn-banner__error">部分卡片加载失败，页面已自动降级显示可用数据。</Text>}
      </View>

      <SectionCard title="天气状态">
        <Text className="home-rn-line">{formatMode(dashboardData.overview?.home_mode)}</Text>
        <Text className="home-rn-line">{formatHomeAssistantStatus(dashboardData.overview?.home_assistant_status)}</Text>
        <Text className="home-rn-line">隐私 {formatPrivacyMode(dashboardData.overview?.privacy_mode)}</Text>
        <Text className="home-rn-line">自动化 {formatAutomationLevel(dashboardData.overview?.automation_level)}</Text>
      </SectionCard>

      <SectionCard title="关键指标">
        <Text className="home-rn-line">{COPY['home.membersAtHome']}：{dashboardData.overview?.member_states.filter(item => item.presence === 'home').length ?? 0}</Text>
        <Text className="home-rn-line">{COPY['home.activeRooms']}：{dashboardData.overview?.room_occupancy.filter(item => item.occupant_count > 0 || item.online_device_count > 0).length ?? dashboardData.rooms.length}</Text>
        <Text className="home-rn-line">{COPY['home.devicesOnline']}：{dashboardData.overview?.device_summary.active ?? dashboardData.devices.filter(item => item.status === 'active').length}</Text>
        <Text className="home-rn-line">{COPY['home.alerts']}：{(dashboardData.reminders?.pending_runs ?? 0) + (dashboardData.overview?.insights.filter(item => item.tone === 'warning' || item.tone === 'danger').length ?? 0)}</Text>
      </SectionCard>

      <SectionCard title={COPY['home.roomStatus']}>
        {loading ? <Text className="home-rn-line">正在加载房间状态...</Text> : roomCards.length > 0 ? roomCards.map(room => (
          <Text key={room.id} className="home-rn-line">{room.name} · {room.secondary} · {room.deviceCount} 设备</Text>
        )) : <Text className="home-rn-line">暂无房间数据</Text>}
      </SectionCard>

      <SectionCard title={COPY['home.memberStatus']}>
        {loading ? <Text className="home-rn-line">正在加载成员状态...</Text> : memberCards.length > 0 ? memberCards.map(member => (
          <Text key={member.id} className="home-rn-line">{member.name} · {member.roleLabel} · {member.badgeStatus === 'resting' ? COPY['member.resting'] : member.badgeStatus === 'home' ? COPY['member.atHome'] : COPY['member.away']}</Text>
        )) : <Text className="home-rn-line">暂无成员数据</Text>}
      </SectionCard>

      <SectionCard title={COPY['home.recentEvents']}>
        {loading ? <Text className="home-rn-line">正在加载最近事件...</Text> : recentEvents.length > 0 ? recentEvents.map((event, index) => (
          <Text key={`${event}-${index}`} className="home-rn-line">{event}</Text>
        )) : <Text className="home-rn-line">{COPY['home.noEventsHint']}</Text>}
      </SectionCard>

      <SectionCard title={COPY['home.quickActions']}>
        <Text className="home-rn-line">{COPY['nav.assistant']} / {COPY['nav.memories']} / {COPY['nav.settings']} / {COPY['nav.family']}</Text>
      </SectionCard>

      <SectionCard title="AI 今日摘要">
        <Text className="home-rn-line">
          {dashboardData.overview?.insights.slice(0, 2).map(item => item.message).join(' ') || '当前还没有新的家庭洞察，系统会在拿到更多上下文后更新这里。'}
        </Text>
      </SectionCard>

      <SectionCard title="设备状态">
        {dashboardData.devices.slice(0, 4).length > 0 ? dashboardData.devices.slice(0, 4).map(device => (
          <Text key={device.id} className="home-rn-line">{device.name} · {device.status === 'active' ? '在线' : '离线'}</Text>
        )) : <Text className="home-rn-line">当前家庭还没有可展示的设备。</Text>}
      </SectionCard>
    </View>
  );
}

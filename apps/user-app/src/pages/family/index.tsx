import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, Text, View } from '@tarojs/components';
import Taro, { useDidShow } from '@tarojs/taro';
import {
  ContextOverviewRead,
  Household,
  Member,
  MemberRelationship,
  ROOM_TYPE_OPTIONS,
  Room,
  formatRoomType,
  listBuiltinLocaleDefinitions,
} from '@familyclaw/user-core';
import { PageSection, StatusCard, userAppTokens } from '@familyclaw/user-ui';
import {
  ActionRow,
  EmptyStateCard,
  FormField,
  OptionPills,
  PrimaryButton,
  SecondaryButton,
  SectionNote,
  TextInput,
} from '../../components/AppUi';
import { MainShellPage } from '../../components/MainShellPage';
import { coreApiClient, needsBlockingSetup, useAppRuntime } from '../../runtime';

type FamilyWorkspace = {
  household: Household | null;
  overview: ContextOverviewRead | null;
  rooms: Room[];
  members: Member[];
  relationships: MemberRelationship[];
  errors: string[];
};

type RoomDraft = {
  name: string;
  room_type: Room['room_type'];
  privacy_level: Room['privacy_level'];
};

type MemberDraft = {
  name: string;
  nickname: string;
  role: Member['role'];
  phone: string;
  birthday: string;
  status: Member['status'];
};

const localeOptions = listBuiltinLocaleDefinitions().map(item => ({
  value: item.id,
  label: item.nativeLabel,
}));

const roomTypeOptions = ROOM_TYPE_OPTIONS.map(item => ({
  value: item.value,
  label: item.label,
}));

const privacyOptions: Array<{ value: Room['privacy_level']; label: string }> = [
  { value: 'public', label: '公开' },
  { value: 'private', label: '私密' },
  { value: 'sensitive', label: '敏感' },
];

const memberRoleOptions: Array<{ value: Member['role']; label: string }> = [
  { value: 'admin', label: '管理员' },
  { value: 'adult', label: '成人' },
  { value: 'child', label: '儿童' },
  { value: 'elder', label: '长辈' },
  { value: 'guest', label: '访客' },
];

const memberStatusOptions: Array<{ value: Member['status']; label: string }> = [
  { value: 'active', label: '启用' },
  { value: 'inactive', label: '停用' },
];

const relationshipOptions: Array<{ value: MemberRelationship['relation_type']; label: string }> = [
  { value: 'spouse', label: '伴侣' },
  { value: 'parent', label: '父母' },
  { value: 'child', label: '子女' },
  { value: 'guardian', label: '监护人' },
  { value: 'caregiver', label: '照护人' },
  { value: 'older_brother', label: '哥哥' },
  { value: 'older_sister', label: '姐姐' },
  { value: 'younger_brother', label: '弟弟' },
  { value: 'younger_sister', label: '妹妹' },
];

function formatMode(mode: ContextOverviewRead['home_mode'] | undefined) {
  switch (mode) {
    case 'home':
      return '居家模式';
    case 'away':
      return '离家模式';
    case 'night':
      return '夜间模式';
    case 'sleep':
      return '睡眠模式';
    case 'custom':
      return '自定义模式';
    default:
      return '未设置';
  }
}

function formatPrivacyMode(mode: ContextOverviewRead['privacy_mode'] | undefined) {
  switch (mode) {
    case 'balanced':
      return '平衡保护';
    case 'strict':
      return '严格保护';
    case 'care':
      return '关怀优先';
    default:
      return '未设置';
  }
}

function formatRole(role: Member['role']) {
  switch (role) {
    case 'admin':
      return '管理员';
    case 'adult':
      return '成人';
    case 'child':
      return '儿童';
    case 'elder':
      return '长辈';
    case 'guest':
      return '访客';
  }
}

function formatRelationship(type: MemberRelationship['relation_type']) {
  const matched = relationshipOptions.find(item => item.value === type);
  return matched?.label ?? type;
}

function getAgeGroup(role: Member['role']): Member['age_group'] {
  switch (role) {
    case 'child':
      return 'child';
    case 'elder':
      return 'elder';
    default:
      return 'adult';
  }
}

export default function FamilyPage() {
  const { bootstrap, loading, refresh } = useAppRuntime();
  const [workspace, setWorkspace] = useState<FamilyWorkspace>({
    household: null,
    overview: null,
    rooms: [],
    members: [],
    relationships: [],
    errors: [],
  });
  const [pageLoading, setPageLoading] = useState(true);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [busyKey, setBusyKey] = useState('');
  const [overviewForm, setOverviewForm] = useState({
    name: '',
    timezone: 'Asia/Shanghai',
    locale: 'zh-CN',
  });
  const [roomForm, setRoomForm] = useState<RoomDraft>({
    name: '',
    room_type: 'living_room',
    privacy_level: 'public',
  });
  const [memberForm, setMemberForm] = useState<MemberDraft>({
    name: '',
    nickname: '',
    role: 'adult',
    phone: '',
    birthday: '',
    status: 'active',
  });
  const [memberAccountForm, setMemberAccountForm] = useState({
    username: '',
    password: '',
  });
  const [relationshipForm, setRelationshipForm] = useState({
    source_member_id: '',
    target_member_id: '',
    relation_type: 'spouse' as MemberRelationship['relation_type'],
  });
  const [roomDrafts, setRoomDrafts] = useState<Record<string, RoomDraft>>({});
  const [memberDrafts, setMemberDrafts] = useState<Record<string, MemberDraft>>({});
  const loadRequestIdRef = useRef(0);
  const activeHouseholdIdRef = useRef('');

  const currentHouseholdId = bootstrap?.currentHousehold?.id ?? '';

  const loadWorkspace = useCallback(async () => {
    const householdId = currentHouseholdId;
    const requestId = ++loadRequestIdRef.current;
    const householdChanged = activeHouseholdIdRef.current !== householdId;

    if (householdChanged) {
      setWorkspace({
        household: null,
        overview: null,
        rooms: [],
        members: [],
        relationships: [],
        errors: [],
      });
      setStatus('');
      setError('');
      setRoomDrafts({});
      setMemberDrafts({});
      setRelationshipForm({
        source_member_id: '',
        target_member_id: '',
        relation_type: 'spouse',
      });
    }

    activeHouseholdIdRef.current = householdId;

    if (!householdId) {
      setPageLoading(false);
      return;
    }

    setPageLoading(true);
    setError('');

    const [householdResult, overviewResult, roomsResult, membersResult, relationshipsResult] = await Promise.allSettled([
      coreApiClient.getHousehold(householdId),
      coreApiClient.getContextOverview(householdId),
      coreApiClient.listRooms(householdId),
      coreApiClient.listMembers(householdId),
      coreApiClient.listMemberRelationships(householdId),
    ]);

    if (requestId !== loadRequestIdRef.current) {
      return;
    }

    const nextWorkspace: FamilyWorkspace = {
      household: householdResult.status === 'fulfilled' ? householdResult.value : null,
      overview: overviewResult.status === 'fulfilled' ? overviewResult.value : null,
      rooms: roomsResult.status === 'fulfilled' ? roomsResult.value.items : [],
      members: membersResult.status === 'fulfilled' ? membersResult.value.items : [],
      relationships: relationshipsResult.status === 'fulfilled' ? relationshipsResult.value.items : [],
      errors: [householdResult, overviewResult, roomsResult, membersResult, relationshipsResult]
        .filter(result => result.status === 'rejected')
        .map(result => result.reason instanceof Error ? result.reason.message : '家庭页数据加载失败'),
    };

    setWorkspace(nextWorkspace);
    setOverviewForm({
      name: nextWorkspace.household?.name ?? bootstrap?.currentHousehold?.name ?? '',
      timezone: nextWorkspace.household?.timezone ?? bootstrap?.currentHousehold?.timezone ?? 'Asia/Shanghai',
      locale: nextWorkspace.household?.locale ?? bootstrap?.currentHousehold?.locale ?? 'zh-CN',
    });
    setRoomDrafts(Object.fromEntries(nextWorkspace.rooms.map(room => [room.id, {
      name: room.name,
      room_type: room.room_type,
      privacy_level: room.privacy_level,
    }])));
    setMemberDrafts(Object.fromEntries(nextWorkspace.members.map(member => [member.id, {
      name: member.name,
      nickname: member.nickname ?? '',
      role: member.role,
      phone: member.phone ?? '',
      birthday: member.birthday ?? '',
      status: member.status,
    }])));
    setPageLoading(false);

    if (nextWorkspace.errors.length > 0) {
      setError('部分家庭数据加载失败，页面已按可用数据降级显示。');
    }
  }, [bootstrap?.currentHousehold?.locale, bootstrap?.currentHousehold?.name, bootstrap?.currentHousehold?.timezone, currentHouseholdId]);

  useEffect(() => {
    if (loading || !bootstrap?.actor?.authenticated || needsBlockingSetup(bootstrap.setupStatus)) {
      return;
    }

    void loadWorkspace();
  }, [bootstrap, loadWorkspace, loading]);

  useDidShow(() => {
    if (!loading && bootstrap?.actor?.authenticated && !needsBlockingSetup(bootstrap.setupStatus)) {
      void loadWorkspace();
    }
  });

  async function runAction(key: string, action: () => Promise<void>, successMessage: string) {
    setBusyKey(key);
    setStatus('');
    setError('');

    try {
      await action();
      await Promise.all([
        loadWorkspace(),
        refresh(),
      ]);
      setStatus(successMessage);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : '家庭操作失败');
    } finally {
      setBusyKey('');
    }
  }

  async function handleDeleteRoom(roomId: string) {
    const result = await Taro.showModal({
      title: '删除房间',
      content: '删除后不会自动恢复，确定继续吗？',
    });

    if (!result.confirm) {
      return;
    }

    await runAction(`delete-room-${roomId}`, () => coreApiClient.deleteRoom(roomId), '房间已删除。');
  }

  async function handleDeleteRelationship(relationshipId: string) {
    const result = await Taro.showModal({
      title: '删除关系',
      content: '关系删除后需要重新创建，确定继续吗？',
    });

    if (!result.confirm) {
      return;
    }

    await runAction(
      `delete-relationship-${relationshipId}`,
      () => coreApiClient.deleteMemberRelationship(relationshipId),
      '成员关系已删除。',
    );
  }

  const groupedRelationships = useMemo(() => {
    return workspace.relationships.reduce<Record<string, MemberRelationship[]>>((acc, item) => {
      const key = item.source_member_id;
      acc[key] = [...(acc[key] ?? []), item];
      return acc;
    }, {});
  }, [workspace.relationships]);

  const memberNameMap = useMemo(
    () => Object.fromEntries(workspace.members.map(member => [member.id, member.name])),
    [workspace.members],
  );

  return (
    <MainShellPage currentNav="family" title="家庭链路已接入真实读写" description="家庭页现在直接拉家庭、房间、成员、关系这些核心数据，不再等着 user-web 托底。">
      <PageSection title="家庭概览" description="先把家庭基本信息、模式摘要和编辑入口立住。">
        <StatusCard label="家庭名称" value={workspace.household?.name ?? bootstrap?.currentHousehold?.name ?? '未读取'} tone="info" />
        <StatusCard label="时区" value={workspace.household?.timezone ?? '未读取'} tone="success" />
        <StatusCard label="默认语言" value={workspace.household?.locale ?? '未读取'} tone="info" />
        <StatusCard label="家庭模式" value={formatMode(workspace.overview?.home_mode)} tone="warning" />
        <StatusCard label="隐私模式" value={formatPrivacyMode(workspace.overview?.privacy_mode)} tone="info" />
        <StatusCard label="地区" value={workspace.household?.region?.display_name ?? workspace.household?.city ?? '未设置'} tone="success" />
        <SectionNote>
          {workspace.overview?.voice_fast_path_enabled ? '语音快通道已开启。' : '语音快通道未开启。'}
          {workspace.overview?.guest_mode_enabled ? ' 访客模式已开启。' : ' 访客模式未开启。'}
          {workspace.overview?.child_protection_enabled ? ' 儿童保护已开启。' : ' 儿童保护未开启。'}
          {workspace.overview?.elder_care_watch_enabled ? ' 长辈关怀已开启。' : ' 长辈关怀未开启。'}
        </SectionNote>
        {pageLoading ? <SectionNote>正在加载家庭工作台...</SectionNote> : null}
        {error ? <SectionNote tone="warning">{error}</SectionNote> : null}
        {status ? <SectionNote tone="success">{status}</SectionNote> : null}
      </PageSection>

      <PageSection title="编辑家庭资料" description="高频链路先把名称、时区、语言做实；地区编辑后面再单独补组件，不在这里糊一层假交互。">
        <FormField label="家庭名称">
          <TextInput value={overviewForm.name} onInput={value => setOverviewForm(current => ({ ...current, name: value }))} />
        </FormField>
        <FormField label="时区">
          <TextInput value={overviewForm.timezone} onInput={value => setOverviewForm(current => ({ ...current, timezone: value }))} />
        </FormField>
        <FormField label="默认语言">
          <OptionPills value={overviewForm.locale} options={localeOptions} onChange={value => setOverviewForm(current => ({ ...current, locale: value }))} />
        </FormField>
        <ActionRow>
          <PrimaryButton
            disabled={!currentHouseholdId || Boolean(busyKey)}
            onClick={() => void runAction(
              'save-household',
              async () => {
                await coreApiClient.updateHousehold(currentHouseholdId, {
                  name: overviewForm.name.trim(),
                  timezone: overviewForm.timezone.trim(),
                  locale: overviewForm.locale,
                });
              },
              '家庭资料已更新。',
            )}
          >
            {busyKey === 'save-household' ? '保存中...' : '保存家庭资料'}
          </PrimaryButton>
        </ActionRow>
      </PageSection>

      <PageSection title="房间管理" description="房间是家庭链路的硬骨头，先把增删改查搬进来。">
        {workspace.rooms.length === 0 && !pageLoading ? (
          <EmptyStateCard title="当前还没有房间" description="先建一个房间，首页和家庭页都会立刻接上。" />
        ) : (
          <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {workspace.rooms.map(room => {
              const draft = roomDrafts[room.id] ?? {
                name: room.name,
                room_type: room.room_type,
                privacy_level: room.privacy_level,
              };

              return (
                <View
                  key={room.id}
                  style={{
                    background: '#f9fbff',
                    border: `1px solid ${userAppTokens.colorBorder}`,
                    borderRadius: userAppTokens.radiusLg,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px',
                    padding: userAppTokens.spacingMd,
                  }}
                >
                  <Text style={{ color: userAppTokens.colorText, fontSize: '28px', fontWeight: '600' }}>
                    {room.name}
                  </Text>
                  <FormField label="房间名称">
                    <TextInput value={draft.name} onInput={value => setRoomDrafts(current => ({ ...current, [room.id]: { ...draft, name: value } }))} />
                  </FormField>
                  <FormField label="房间类型">
                    <OptionPills value={draft.room_type} options={roomTypeOptions} onChange={value => setRoomDrafts(current => ({ ...current, [room.id]: { ...draft, room_type: value } }))} />
                  </FormField>
                  <FormField label="隐私级别">
                    <OptionPills value={draft.privacy_level} options={privacyOptions} onChange={value => setRoomDrafts(current => ({ ...current, [room.id]: { ...draft, privacy_level: value } }))} />
                  </FormField>
                  <ActionRow>
                    <PrimaryButton
                      disabled={Boolean(busyKey)}
                      onClick={() => void runAction(
                        `save-room-${room.id}`,
                        async () => {
                          await coreApiClient.updateRoom(room.id, draft);
                        },
                        `房间“${draft.name}”已更新。`,
                      )}
                    >
                      {busyKey === `save-room-${room.id}` ? '保存中...' : '保存房间'}
                    </PrimaryButton>
                    <SecondaryButton disabled={Boolean(busyKey)} onClick={() => void handleDeleteRoom(room.id)}>
                      删除房间
                    </SecondaryButton>
                  </ActionRow>
                </View>
              );
            })}
          </View>
        )}

        <View
          style={{
            background: '#ffffff',
            border: `1px dashed ${userAppTokens.colorBorder}`,
            borderRadius: userAppTokens.radiusLg,
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            padding: userAppTokens.spacingMd,
            marginTop: '12px',
          }}
        >
          <Text style={{ color: userAppTokens.colorText, fontSize: '28px', fontWeight: '600' }}>
            新建房间
          </Text>
          <FormField label="房间名称">
            <TextInput value={roomForm.name} placeholder="例如：客厅 / 长辈房" onInput={value => setRoomForm(current => ({ ...current, name: value }))} />
          </FormField>
          <FormField label="房间类型">
            <OptionPills value={roomForm.room_type} options={roomTypeOptions} onChange={value => setRoomForm(current => ({ ...current, room_type: value }))} />
          </FormField>
          <FormField label="隐私级别">
            <OptionPills value={roomForm.privacy_level} options={privacyOptions} onChange={value => setRoomForm(current => ({ ...current, privacy_level: value }))} />
          </FormField>
          <ActionRow>
            <PrimaryButton
              disabled={!currentHouseholdId || !roomForm.name.trim() || Boolean(busyKey)}
              onClick={() => void runAction(
                'create-room',
                async () => {
                  await coreApiClient.createRoom({
                    household_id: currentHouseholdId,
                    name: roomForm.name.trim(),
                    room_type: roomForm.room_type,
                    privacy_level: roomForm.privacy_level,
                  });
                  setRoomForm({
                    name: '',
                    room_type: 'living_room',
                    privacy_level: 'public',
                  });
                },
                '房间已创建。',
              )}
            >
              {busyKey === 'create-room' ? '创建中...' : '新建房间'}
            </PrimaryButton>
          </ActionRow>
        </View>
      </PageSection>

      <PageSection title="成员管理" description="成员资料和账号关联不能再留在旧页面，这里直接搬成可用表单。">
        {workspace.members.length === 0 && !pageLoading ? (
          <EmptyStateCard title="当前还没有成员" description="先创建成员，家庭关系和首页状态卡才有数据。"/>
        ) : (
          <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {workspace.members.map(member => {
              const draft = memberDrafts[member.id] ?? {
                name: member.name,
                nickname: member.nickname ?? '',
                role: member.role,
                phone: member.phone ?? '',
                birthday: member.birthday ?? '',
                status: member.status,
              };

              return (
                <View
                  key={member.id}
                  style={{
                    background: '#f9fbff',
                    border: `1px solid ${userAppTokens.colorBorder}`,
                    borderRadius: userAppTokens.radiusLg,
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px',
                    padding: userAppTokens.spacingMd,
                  }}
                >
                  <Text style={{ color: userAppTokens.colorText, fontSize: '28px', fontWeight: '600' }}>
                    {member.name} · {formatRole(member.role)}
                  </Text>
                  <FormField label="成员姓名">
                    <TextInput value={draft.name} onInput={value => setMemberDrafts(current => ({ ...current, [member.id]: { ...draft, name: value } }))} />
                  </FormField>
                  <FormField label="昵称">
                    <TextInput value={draft.nickname} onInput={value => setMemberDrafts(current => ({ ...current, [member.id]: { ...draft, nickname: value } }))} />
                  </FormField>
                  <FormField label="角色">
                    <OptionPills value={draft.role} options={memberRoleOptions} onChange={value => setMemberDrafts(current => ({ ...current, [member.id]: { ...draft, role: value } }))} />
                  </FormField>
                  <FormField label="手机号">
                    <TextInput value={draft.phone} onInput={value => setMemberDrafts(current => ({ ...current, [member.id]: { ...draft, phone: value } }))} />
                  </FormField>
                  <FormField label="生日">
                    <TextInput value={draft.birthday} placeholder="YYYY-MM-DD" onInput={value => setMemberDrafts(current => ({ ...current, [member.id]: { ...draft, birthday: value } }))} />
                  </FormField>
                  <FormField label="状态">
                    <OptionPills value={draft.status} options={memberStatusOptions} onChange={value => setMemberDrafts(current => ({ ...current, [member.id]: { ...draft, status: value } }))} />
                  </FormField>
                  <ActionRow>
                    <PrimaryButton
                      disabled={Boolean(busyKey)}
                      onClick={() => void runAction(
                        `save-member-${member.id}`,
                        async () => {
                          await coreApiClient.updateMember(member.id, {
                            name: draft.name.trim(),
                            nickname: draft.nickname.trim() || null,
                            role: draft.role,
                            phone: draft.phone.trim() || null,
                            birthday: draft.birthday.trim() || null,
                            status: draft.status,
                            age_group: getAgeGroup(draft.role),
                          });
                        },
                        `成员“${draft.name}”已更新。`,
                      )}
                    >
                      {busyKey === `save-member-${member.id}` ? '保存中...' : '保存成员'}
                    </PrimaryButton>
                  </ActionRow>
                </View>
              );
            })}
          </View>
        )}

        <View
          style={{
            background: '#ffffff',
            border: `1px dashed ${userAppTokens.colorBorder}`,
            borderRadius: userAppTokens.radiusLg,
            display: 'flex',
            flexDirection: 'column',
            gap: '12px',
            padding: userAppTokens.spacingMd,
            marginTop: '12px',
          }}
        >
          <Text style={{ color: userAppTokens.colorText, fontSize: '28px', fontWeight: '600' }}>
            新建成员
          </Text>
          <FormField label="成员姓名">
            <TextInput value={memberForm.name} onInput={value => setMemberForm(current => ({ ...current, name: value }))} />
          </FormField>
          <FormField label="昵称">
            <TextInput value={memberForm.nickname} onInput={value => setMemberForm(current => ({ ...current, nickname: value }))} />
          </FormField>
          <FormField label="角色">
            <OptionPills value={memberForm.role} options={memberRoleOptions} onChange={value => setMemberForm(current => ({ ...current, role: value }))} />
          </FormField>
          <FormField label="手机号">
            <TextInput value={memberForm.phone} onInput={value => setMemberForm(current => ({ ...current, phone: value }))} />
          </FormField>
          <FormField label="生日">
            <TextInput value={memberForm.birthday} placeholder="YYYY-MM-DD" onInput={value => setMemberForm(current => ({ ...current, birthday: value }))} />
          </FormField>
          <FormField label="登录账号（可选）" hint="如果要一次性创建正式账号，就把账号和密码一起填上。">
            <TextInput value={memberAccountForm.username} onInput={value => setMemberAccountForm(current => ({ ...current, username: value }))} />
          </FormField>
          <FormField label="登录密码（可选）">
            <TextInput value={memberAccountForm.password} password onInput={value => setMemberAccountForm(current => ({ ...current, password: value }))} />
          </FormField>
          <ActionRow>
            <PrimaryButton
              disabled={!currentHouseholdId || !memberForm.name.trim() || Boolean(busyKey)}
              onClick={() => void runAction(
                'create-member',
                async () => {
                  const member = await coreApiClient.createMember({
                    household_id: currentHouseholdId,
                    name: memberForm.name.trim(),
                    nickname: memberForm.nickname.trim() || null,
                    role: memberForm.role,
                    phone: memberForm.phone.trim() || null,
                    birthday: memberForm.birthday.trim() || null,
                    status: memberForm.status,
                    age_group: getAgeGroup(memberForm.role),
                  });

                  if (memberAccountForm.username.trim() && memberAccountForm.password) {
                    await coreApiClient.createHouseholdAccount({
                      household_id: currentHouseholdId,
                      member_id: member.id,
                      username: memberAccountForm.username.trim(),
                      password: memberAccountForm.password,
                      must_change_password: false,
                    });
                  }

                  setMemberForm({
                    name: '',
                    nickname: '',
                    role: 'adult',
                    phone: '',
                    birthday: '',
                    status: 'active',
                  });
                  setMemberAccountForm({
                    username: '',
                    password: '',
                  });
                },
                '成员已创建。',
              )}
            >
              {busyKey === 'create-member' ? '创建中...' : '新建成员'}
            </PrimaryButton>
          </ActionRow>
        </View>
      </PageSection>

      <PageSection title="成员关系" description="关系图谱先不硬搬，先把关系增删和列表读写做实。">
        {workspace.members.length < 2 ? (
          <EmptyStateCard title="成员还不够" description="至少要有两位成员，关系管理才有意义。" />
        ) : (
          <>
            <FormField label="关系发起成员">
              <OptionPills
                value={relationshipForm.source_member_id}
                options={workspace.members.map(member => ({ value: member.id, label: member.name }))}
                onChange={value => setRelationshipForm(current => ({ ...current, source_member_id: value }))}
              />
            </FormField>
            <FormField label="关系目标成员">
              <OptionPills
                value={relationshipForm.target_member_id}
                options={workspace.members.filter(member => member.id !== relationshipForm.source_member_id).map(member => ({ value: member.id, label: member.name }))}
                onChange={value => setRelationshipForm(current => ({ ...current, target_member_id: value }))}
              />
            </FormField>
            <FormField label="关系类型">
              <OptionPills value={relationshipForm.relation_type} options={relationshipOptions} onChange={value => setRelationshipForm(current => ({ ...current, relation_type: value }))} />
            </FormField>
            <ActionRow>
              <PrimaryButton
                disabled={!currentHouseholdId || !relationshipForm.source_member_id || !relationshipForm.target_member_id || Boolean(busyKey)}
                onClick={() => void runAction(
                  'create-relationship',
                  async () => {
                    await coreApiClient.createMemberRelationship({
                      household_id: currentHouseholdId,
                      source_member_id: relationshipForm.source_member_id,
                      target_member_id: relationshipForm.target_member_id,
                      relation_type: relationshipForm.relation_type,
                      visibility_scope: 'family',
                      delegation_scope: 'none',
                    });
                    setRelationshipForm({
                      source_member_id: '',
                      target_member_id: '',
                      relation_type: 'spouse',
                    });
                  },
                  '成员关系已创建。',
                )}
              >
                {busyKey === 'create-relationship' ? '创建中...' : '新增关系'}
              </PrimaryButton>
            </ActionRow>
          </>
        )}

        {workspace.relationships.length === 0 ? (
          <EmptyStateCard title="还没有关系" description="先选成员和关系类型，建立第一条关系。" />
        ) : (
          <View style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '12px' }}>
            {Object.entries(groupedRelationships).map(([sourceMemberId, items]) => (
              <View
                key={sourceMemberId}
                style={{
                  background: '#f9fbff',
                  border: `1px solid ${userAppTokens.colorBorder}`,
                  borderRadius: userAppTokens.radiusLg,
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '12px',
                  padding: userAppTokens.spacingMd,
                }}
              >
                <Text style={{ color: userAppTokens.colorText, fontSize: '28px', fontWeight: '600' }}>
                  {memberNameMap[sourceMemberId] ?? sourceMemberId} 的关系
                </Text>
                {items.map(item => (
                  <View
                    key={item.id}
                    style={{
                      background: '#ffffff',
                      border: `1px solid ${userAppTokens.colorBorder}`,
                      borderRadius: userAppTokens.radiusMd,
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '8px',
                      padding: userAppTokens.spacingSm,
                    }}
                  >
                    <Text style={{ color: userAppTokens.colorText, fontSize: '24px' }}>
                      {formatRelationship(item.relation_type)} → {memberNameMap[item.target_member_id] ?? item.target_member_id}
                    </Text>
                    <ActionRow>
                      <SecondaryButton disabled={Boolean(busyKey)} onClick={() => void handleDeleteRelationship(item.id)}>
                        删除关系
                      </SecondaryButton>
                    </ActionRow>
                  </View>
                ))}
              </View>
            ))}
          </View>
        )}
      </PageSection>
    </MainShellPage>
  );
}

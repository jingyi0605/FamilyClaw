import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button, Text, View } from '@tarojs/components';
import Taro, { useDidShow } from '@tarojs/taro';
import {
  PluginJobListItemRead,
  PluginManifestType,
  PluginMountRead,
  PluginRegistryItem,
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
import { coreApiClient, useAppRuntime } from '../../runtime';

type PluginWorkspace = {
  plugins: PluginRegistryItem[];
  mounts: PluginMountRead[];
};

type PluginMountForm = {
  sourceType: 'official' | 'third_party';
  pluginRoot: string;
  manifestPath: string;
  pythonPath: string;
  workingDir: string;
  timeoutSeconds: string;
  enabled: 'true' | 'false';
};

const PLUGIN_TYPE_LABELS: Record<PluginManifestType, string> = {
  connector: '连接器',
  'memory-ingestor': '记忆摄取',
  action: '动作',
  'agent-skill': 'Agent 技能',
  channel: '通讯通道',
  'locale-pack': '语言包',
  'region-provider': '地区提供者',
};

const sourceOptions: Array<{ value: PluginMountForm['sourceType']; label: string }> = [
  { value: 'third_party', label: '第三方' },
  { value: 'official', label: '官方' },
];

const enabledOptions: Array<{ value: PluginMountForm['enabled']; label: string }> = [
  { value: 'true', label: '挂载后启用' },
  { value: 'false', label: '先挂载后停用' },
];

function buildInitialMountForm(): PluginMountForm {
  return {
    sourceType: 'third_party',
    pluginRoot: '',
    manifestPath: '',
    pythonPath: '',
    workingDir: '',
    timeoutSeconds: '30',
    enabled: 'true',
  };
}

function formatRelativeTime(value: string | null | undefined) {
  if (!value) {
    return '暂无';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const diffMinutes = Math.max(1, Math.round((Date.now() - date.getTime()) / 60000));
  if (diffMinutes < 60) {
    return `${diffMinutes} 分钟前`;
  }

  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours} 小时前`;
  }

  return `${Math.round(diffHours / 24)} 天前`;
}

function formatSourceType(sourceType: PluginRegistryItem['source_type'] | PluginMountRead['source_type']) {
  switch (sourceType) {
    case 'builtin':
      return '内置';
    case 'official':
      return '官方';
    default:
      return '第三方';
  }
}

function formatRiskLevel(riskLevel: PluginRegistryItem['risk_level']) {
  switch (riskLevel) {
    case 'low':
      return '低风险';
    case 'medium':
      return '中风险';
    default:
      return '高风险';
  }
}

function formatJobStatus(status: PluginJobListItemRead['job']['status']) {
  switch (status) {
    case 'queued':
      return '排队中';
    case 'running':
      return '执行中';
    case 'retry_waiting':
      return '等待重试';
    case 'waiting_response':
      return '等待响应';
    case 'succeeded':
      return '已成功';
    case 'failed':
      return '已失败';
    default:
      return '已取消';
  }
}

function summarizeEntrypoints(plugin: PluginRegistryItem) {
  const entrypoints = Object.entries(plugin.entrypoints ?? {})
    .filter(([, value]) => Boolean(value))
    .map(([key]) => key);

  if (entrypoints.length === 0) {
    return '没有公开入口';
  }

  return entrypoints.join('、');
}

function sortPlugins(plugins: PluginRegistryItem[]) {
  return [...plugins].sort((left, right) => {
    if (left.enabled !== right.enabled) {
      return left.enabled ? -1 : 1;
    }

    if (left.source_type !== right.source_type) {
      const order: Record<PluginRegistryItem['source_type'], number> = {
        builtin: 0,
        official: 1,
        third_party: 2,
      };
      return order[left.source_type] - order[right.source_type];
    }

    return left.name.localeCompare(right.name, 'zh-CN');
  });
}

export default function PluginsPage() {
  const { bootstrap, refresh } = useAppRuntime();
  const [workspace, setWorkspace] = useState<PluginWorkspace>({
    plugins: [],
    mounts: [],
  });
  const [selectedPluginId, setSelectedPluginId] = useState('');
  const [recentJobs, setRecentJobs] = useState<PluginJobListItemRead[]>([]);
  const [mountForm, setMountForm] = useState<PluginMountForm>(buildInitialMountForm());
  const [pageLoading, setPageLoading] = useState(true);
  const [jobsLoading, setJobsLoading] = useState(false);
  const [busyKey, setBusyKey] = useState('');
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');
  const [jobsError, setJobsError] = useState('');
  const loadRequestIdRef = useRef(0);
  const jobsRequestIdRef = useRef(0);
  const activeHouseholdIdRef = useRef('');

  const currentHouseholdId = bootstrap?.currentHousehold?.id ?? '';
  const currentHouseholdName = bootstrap?.currentHousehold?.name ?? '未选定家庭';

  const mountMap = useMemo(
    () => new Map(workspace.mounts.map(item => [item.plugin_id, item])),
    [workspace.mounts],
  );
  const selectedPlugin = useMemo(
    () => workspace.plugins.find(plugin => plugin.id === selectedPluginId) ?? null,
    [selectedPluginId, workspace.plugins],
  );
  const selectedMount = selectedPlugin ? mountMap.get(selectedPlugin.id) ?? null : null;
  const enabledCount = useMemo(
    () => workspace.plugins.filter(plugin => plugin.enabled).length,
    [workspace.plugins],
  );
  const mountedCount = workspace.mounts.length;

  const loadWorkspace = useCallback(async (preferredSelectedId?: string | null) => {
    const householdId = currentHouseholdId;
    const requestId = ++loadRequestIdRef.current;
    const householdChanged = activeHouseholdIdRef.current !== householdId;

    if (householdChanged) {
      setWorkspace({ plugins: [], mounts: [] });
      setSelectedPluginId('');
      setRecentJobs([]);
      setStatus('');
      setError('');
      setJobsError('');
    }

    activeHouseholdIdRef.current = householdId;

    if (!householdId) {
      setPageLoading(false);
      return;
    }

    setPageLoading(true);
    setError('');

    try {
      const [pluginRegistry, mounts] = await Promise.all([
        coreApiClient.listRegisteredPlugins(householdId),
        coreApiClient.listPluginMounts(householdId),
      ]);

      if (requestId !== loadRequestIdRef.current) {
        return;
      }

      const sortedPlugins = sortPlugins(pluginRegistry.items);
      setWorkspace({
        plugins: sortedPlugins,
        mounts,
      });
      setSelectedPluginId(current => {
        if (preferredSelectedId === null) {
          return sortedPlugins[0]?.id ?? '';
        }
        if (preferredSelectedId && sortedPlugins.some(plugin => plugin.id === preferredSelectedId)) {
          return preferredSelectedId;
        }
        if (current && sortedPlugins.some(plugin => plugin.id === current)) {
          return current;
        }
        return sortedPlugins[0]?.id ?? '';
      });
    } catch (loadError) {
      if (requestId === loadRequestIdRef.current) {
        setWorkspace({ plugins: [], mounts: [] });
        setSelectedPluginId('');
        setError(loadError instanceof Error ? loadError.message : '插件列表加载失败');
      }
    } finally {
      if (requestId === loadRequestIdRef.current) {
        setPageLoading(false);
      }
    }
  }, [currentHouseholdId]);

  const loadJobs = useCallback(async (pluginId: string) => {
    if (!currentHouseholdId || !pluginId) {
      setRecentJobs([]);
      setJobsError('');
      return;
    }

    const requestId = ++jobsRequestIdRef.current;
    setJobsLoading(true);
    setJobsError('');

    try {
      const result = await coreApiClient.listPluginJobs(currentHouseholdId, {
        plugin_id: pluginId,
        page_size: 5,
      });
      if (requestId !== jobsRequestIdRef.current) {
        return;
      }
      setRecentJobs(result.items);
    } catch (loadError) {
      if (requestId === jobsRequestIdRef.current) {
        setRecentJobs([]);
        setJobsError(loadError instanceof Error ? loadError.message : '插件任务加载失败');
      }
    } finally {
      if (requestId === jobsRequestIdRef.current) {
        setJobsLoading(false);
      }
    }
  }, [currentHouseholdId]);

  useEffect(() => {
    void loadWorkspace();
  }, [loadWorkspace]);

  useDidShow(() => {
    if (currentHouseholdId) {
      void loadWorkspace(selectedPluginId || undefined);
    }
  });

  useEffect(() => {
    if (!selectedPluginId) {
      setRecentJobs([]);
      setJobsError('');
      return;
    }

    void loadJobs(selectedPluginId);
  }, [loadJobs, selectedPluginId]);

  async function runAction(
    key: string,
    action: () => Promise<void>,
    successMessage: string,
    preferredSelectedId?: string | null,
  ) {
    setBusyKey(key);
    setStatus('');
    setError('');

    try {
      await action();
      await Promise.all([
        loadWorkspace(preferredSelectedId),
        refresh(),
      ]);
      setStatus(successMessage);
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : '插件操作失败');
    } finally {
      setBusyKey('');
    }
  }

  async function handleTogglePlugin(plugin: PluginRegistryItem) {
    if (!currentHouseholdId) {
      return;
    }

    await runAction(
      `toggle-${plugin.id}`,
      async () => {
        await coreApiClient.updatePluginState(currentHouseholdId, plugin.id, {
          enabled: !plugin.enabled,
        });
      },
      plugin.enabled ? `插件“${plugin.name}”已停用。` : `插件“${plugin.name}”已启用。`,
      plugin.id,
    );
  }

  async function handleDeleteMountedPlugin(plugin: PluginRegistryItem) {
    if (!currentHouseholdId) {
      return;
    }

    const result = await Taro.showModal({
      title: '删除插件挂载',
      content: `确定删除插件“${plugin.name}”的当前家庭挂载吗？删除后需要重新挂载才能继续使用。`,
    });

    if (!result.confirm) {
      return;
    }

    await runAction(
      `delete-${plugin.id}`,
      async () => {
        await coreApiClient.deletePluginMount(currentHouseholdId, plugin.id);
      },
      `插件“${plugin.name}”的挂载已删除。`,
      null,
    );
  }

  async function handleMountPlugin() {
    if (!currentHouseholdId) {
      setError('当前没有可用的家庭上下文');
      return;
    }

    if (!mountForm.pluginRoot.trim() || !mountForm.pythonPath.trim()) {
      setError('插件目录和 Python 路径都必须填写');
      return;
    }

    const parsedTimeout = Number.parseInt(mountForm.timeoutSeconds.trim(), 10);
    if (Number.isNaN(parsedTimeout) || parsedTimeout < 1 || parsedTimeout > 300) {
      setError('超时时间必须是 1 到 300 之间的整数秒');
      return;
    }

    setBusyKey('mount');
    setStatus('');
    setError('');

    try {
      const created = await coreApiClient.createPluginMount(currentHouseholdId, {
        source_type: mountForm.sourceType,
        plugin_root: mountForm.pluginRoot.trim(),
        manifest_path: mountForm.manifestPath.trim() || null,
        python_path: mountForm.pythonPath.trim(),
        working_dir: mountForm.workingDir.trim() || null,
        timeout_seconds: parsedTimeout,
        enabled: mountForm.enabled === 'true',
      });
      setMountForm(buildInitialMountForm());
      await Promise.all([
        loadWorkspace(created.plugin_id),
        refresh(),
      ]);
      setStatus(`插件“${created.name}”已挂载。`);
    } catch (mountError) {
      setError(mountError instanceof Error ? mountError.message : '插件挂载失败');
    } finally {
      setBusyKey('');
    }
  }

  return (
    <MainShellPage
      currentNav="plugins"
      title="插件管理已迁入新应用"
      description="这一页只做插件主链：列表、详情、挂载、启停、删除和最近任务，不把 user-web 的浏览器壳整坨搬回来。"
    >
      <PageSection title="插件状态总览" description="先看清当前家庭到底挂了多少插件，哪些已经启用。">
        <StatusCard label="当前家庭" value={currentHouseholdName} tone="info" />
        <StatusCard label="已注册插件" value={`${workspace.plugins.length}`} tone="success" />
        <StatusCard label="已启用插件" value={`${enabledCount}`} tone="info" />
        <StatusCard label="已挂载插件" value={`${mountedCount}`} tone="warning" />
        {pageLoading ? <SectionNote>正在读取当前家庭的插件清单...</SectionNote> : null}
        {status ? <SectionNote tone="success">{status}</SectionNote> : null}
        {error ? <SectionNote tone="warning">{error}</SectionNote> : null}
      </PageSection>

      <PageSection title="插件列表" description="列表先做到真能切换、启停和删除，不追求旧页那堆视图切换。">
        {pageLoading ? (
          <EmptyStateCard title="正在加载插件" description="共享插件 API 正在返回当前家庭的已注册插件。" />
        ) : workspace.plugins.length === 0 ? (
          <EmptyStateCard title="当前还没有插件" description="内置插件未注册，或者当前家庭暂时没有可见插件。" />
        ) : (
          <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {workspace.plugins.map(plugin => {
              const active = plugin.id === selectedPluginId;
              const mounted = mountMap.has(plugin.id);
              const toggleKey = `toggle-${plugin.id}`;
              const deleteKey = `delete-${plugin.id}`;

              return (
                <View
                  key={plugin.id}
                  style={{
                    background: active ? '#eef5ff' : '#ffffff',
                    border: `1px solid ${active ? userAppTokens.colorPrimary : userAppTokens.colorBorder}`,
                    borderRadius: userAppTokens.radiusLg,
                    padding: userAppTokens.spacingMd,
                  }}
                >
                  <View style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                    <View style={{ alignItems: 'center', display: 'flex', flexDirection: 'row', justifyContent: 'space-between', gap: '12px' }}>
                      <Text style={{ color: userAppTokens.colorText, flex: 1, fontSize: '28px', fontWeight: '600' }}>
                        {plugin.name}
                      </Text>
                      <Text style={{ color: plugin.enabled ? userAppTokens.colorSuccess : userAppTokens.colorWarning, fontSize: '22px' }}>
                        {plugin.enabled ? '已启用' : '已停用'}
                      </Text>
                    </View>
                    <Text style={{ color: userAppTokens.colorMuted, fontSize: '20px', lineHeight: '1.6' }}>
                      {plugin.id} · v{plugin.version} · {formatSourceType(plugin.source_type)} · {formatRiskLevel(plugin.risk_level)}
                    </Text>
                    <Text style={{ color: userAppTokens.colorText, fontSize: '22px', lineHeight: '1.6' }}>
                      类型：{plugin.types.map(type => PLUGIN_TYPE_LABELS[type] ?? type).join('、')}
                    </Text>
                    <Text style={{ color: userAppTokens.colorMuted, fontSize: '22px', lineHeight: '1.6' }}>
                      {mounted ? '当前家庭已挂载' : plugin.source_type === 'builtin' ? '内置插件，无需挂载' : '当前家庭未挂载'}
                    </Text>
                  </View>
                  <ActionRow>
                    <PrimaryButton disabled={Boolean(busyKey)} onClick={() => setSelectedPluginId(plugin.id)}>
                      {active ? '当前详情' : '查看详情'}
                    </PrimaryButton>
                    <SecondaryButton disabled={Boolean(busyKey)} onClick={() => void handleTogglePlugin(plugin)}>
                      {busyKey === toggleKey ? '处理中...' : plugin.enabled ? '停用' : '启用'}
                    </SecondaryButton>
                    {mounted ? (
                      <Button
                        disabled={Boolean(busyKey)}
                        onClick={() => void handleDeleteMountedPlugin(plugin)}
                        style={{
                          background: '#fff5f2',
                          border: `1px solid ${userAppTokens.colorWarning}`,
                          borderRadius: userAppTokens.radiusMd,
                          color: userAppTokens.colorWarning,
                          fontSize: '24px',
                        }}
                      >
                        {busyKey === deleteKey ? '删除中...' : '删除挂载'}
                      </Button>
                    ) : null}
                  </ActionRow>
                </View>
              );
            })}
          </View>
        )}
      </PageSection>

      <PageSection title="插件详情" description="详情里只保留最常用的判断信息和最近任务，不做厚重抽屉。">
        {!selectedPlugin ? (
          <EmptyStateCard title="还没有选中插件" description="先从上面的列表选一个插件，这里才有详情和任务记录。" />
        ) : (
          <View style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <View
              style={{
                background: '#f9fbff',
                border: `1px solid ${userAppTokens.colorBorder}`,
                borderRadius: userAppTokens.radiusLg,
                display: 'flex',
                flexDirection: 'column',
                gap: '10px',
                padding: userAppTokens.spacingMd,
              }}
            >
              <Text style={{ color: userAppTokens.colorText, fontSize: '28px', fontWeight: '600' }}>
                {selectedPlugin.name}
              </Text>
              <Text style={{ color: userAppTokens.colorMuted, fontSize: '22px' }}>
                ID：{selectedPlugin.id}
              </Text>
              <Text style={{ color: userAppTokens.colorMuted, fontSize: '22px' }}>
                版本：v{selectedPlugin.version}
              </Text>
              <Text style={{ color: userAppTokens.colorText, fontSize: '22px' }}>
                来源：{formatSourceType(selectedPlugin.source_type)} · 风险：{formatRiskLevel(selectedPlugin.risk_level)}
              </Text>
              <Text style={{ color: userAppTokens.colorText, fontSize: '22px' }}>
                类型：{selectedPlugin.types.map(type => PLUGIN_TYPE_LABELS[type] ?? type).join('、')}
              </Text>
              <Text style={{ color: userAppTokens.colorText, fontSize: '22px' }}>
                入口：{summarizeEntrypoints(selectedPlugin)}
              </Text>
              <Text style={{ color: userAppTokens.colorText, fontSize: '22px' }}>
                权限：{selectedPlugin.permissions.length ? selectedPlugin.permissions.join('、') : '无额外权限'}
              </Text>
              <Text style={{ color: userAppTokens.colorText, fontSize: '22px' }}>
                触发器：{selectedPlugin.triggers.length ? selectedPlugin.triggers.join('、') : '暂无'}
              </Text>
              <Text style={{ color: userAppTokens.colorText, fontSize: '22px' }}>
                当前家庭状态：{selectedPlugin.enabled ? '已启用' : '已停用'}
              </Text>
              {selectedMount ? (
                <>
                  <Text style={{ color: userAppTokens.colorMuted, fontSize: '22px' }}>
                    挂载目录：{selectedMount.plugin_root}
                  </Text>
                  <Text style={{ color: userAppTokens.colorMuted, fontSize: '22px' }}>
                    Python：{selectedMount.python_path}
                  </Text>
                  <Text style={{ color: userAppTokens.colorMuted, fontSize: '22px' }}>
                    挂载更新：{formatRelativeTime(selectedMount.updated_at)}
                  </Text>
                </>
              ) : null}
              {selectedPlugin.disabled_reason ? (
                <SectionNote tone="warning">{selectedPlugin.disabled_reason}</SectionNote>
              ) : null}
              {selectedPlugin.source_type === 'third_party' ? (
                <SectionNote tone="warning">第三方插件会跑你提供的本地代码和解释器路径，这不是玩具，别乱挂不可信目录。</SectionNote>
              ) : null}
            </View>

            {jobsLoading ? (
              <EmptyStateCard title="正在加载最近任务" description="当前插件的最近任务正在同步。" />
            ) : jobsError ? (
              <EmptyStateCard title="最近任务暂时不可用" description={jobsError} />
            ) : recentJobs.length === 0 ? (
              <EmptyStateCard title="当前没有最近任务" description="这个插件还没有公开任务记录，或者最近没有跑过。" />
            ) : (
              <View style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {recentJobs.map(item => (
                  <View
                    key={item.job.id}
                    style={{
                      background: '#ffffff',
                      border: `1px solid ${userAppTokens.colorBorder}`,
                      borderRadius: userAppTokens.radiusLg,
                      padding: userAppTokens.spacingMd,
                    }}
                  >
                    <Text style={{ color: userAppTokens.colorText, display: 'block', fontSize: '24px', fontWeight: '600' }}>
                      {item.job.trigger} · {formatJobStatus(item.job.status)}
                    </Text>
                    <Text style={{ color: userAppTokens.colorMuted, display: 'block', fontSize: '20px', marginTop: '6px' }}>
                      尝试 {item.job.current_attempt}/{item.job.max_attempts} · {formatRelativeTime(item.job.created_at)}
                    </Text>
                    {item.job.last_error_message ? (
                      <SectionNote tone="warning">{item.job.last_error_message}</SectionNote>
                    ) : null}
                    {item.allowed_actions.length > 0 ? (
                      <SectionNote>允许动作：{item.allowed_actions.join('、')}</SectionNote>
                    ) : null}
                  </View>
                ))}
              </View>
            )}
          </View>
        )}
      </PageSection>

      <PageSection title="挂载插件" description="先把最小可用挂载链路做实，第三方和官方插件都走同一套共享 API。">
        <FormField label="插件来源">
          <OptionPills
            value={mountForm.sourceType}
            options={sourceOptions}
            onChange={value => setMountForm(current => ({ ...current, sourceType: value }))}
          />
        </FormField>
        <FormField label="插件目录" hint="这里填插件根目录。后端会按 manifest 和运行时规则自己识别，不需要页面瞎猜。">
          <TextInput
            value={mountForm.pluginRoot}
            placeholder="例如：C:\\plugins\\my-plugin"
            onInput={value => setMountForm(current => ({ ...current, pluginRoot: value }))}
          />
        </FormField>
        <FormField label="Manifest 路径（可选）">
          <TextInput
            value={mountForm.manifestPath}
            placeholder="不填则按默认 manifest 路径探测"
            onInput={value => setMountForm(current => ({ ...current, manifestPath: value }))}
          />
        </FormField>
        <FormField label="Python 路径">
          <TextInput
            value={mountForm.pythonPath}
            placeholder="例如：C:\\Python311\\python.exe"
            onInput={value => setMountForm(current => ({ ...current, pythonPath: value }))}
          />
        </FormField>
        <FormField label="工作目录（可选）">
          <TextInput
            value={mountForm.workingDir}
            placeholder="不填则由后端按插件目录处理"
            onInput={value => setMountForm(current => ({ ...current, workingDir: value }))}
          />
        </FormField>
        <FormField label="超时时间（秒）">
          <TextInput
            value={mountForm.timeoutSeconds}
            placeholder="1 到 300"
            onInput={value => setMountForm(current => ({ ...current, timeoutSeconds: value }))}
          />
        </FormField>
        <FormField label="挂载后状态">
          <OptionPills
            value={mountForm.enabled}
            options={enabledOptions}
            onChange={value => setMountForm(current => ({ ...current, enabled: value }))}
          />
        </FormField>
        <ActionRow>
          <PrimaryButton disabled={Boolean(busyKey)} onClick={() => void handleMountPlugin()}>
            {busyKey === 'mount' ? '挂载中...' : '挂载插件'}
          </PrimaryButton>
          <SecondaryButton disabled={Boolean(busyKey)} onClick={() => setMountForm(buildInitialMountForm())}>
            重置表单
          </SecondaryButton>
        </ActionRow>
        <SectionNote>
          这轮先迁最小闭环，不做插件市场和复杂任务流编辑。真问题先解决，别拿花哨界面掩盖数据链路没通。
        </SectionNote>
      </PageSection>
    </MainShellPage>
  );
}

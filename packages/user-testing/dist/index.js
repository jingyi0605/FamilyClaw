// packages/user-testing/src/parity/registry.ts
function countParityItems(registry) {
  return registry.items.reduce(
    (summary, item) => {
      summary[item.status] += 1;
      return summary;
    },
    {
      blocked: 0,
      dropped: 0,
      in_progress: 0,
      not_started: 0,
      ready: 0
    }
  );
}

// packages/user-testing/src/parity/user-web-pages.ts
var userWebPageParity = [
  {
    feature_key: "shared-auth-runtime",
    legacy_entry: "apps/user-web/src/state/auth.tsx",
    new_entry: "packages/user-core/src/state/auth.ts",
    status: "ready",
    blocking_reason: "\u8BA4\u8BC1\u6E05\u7406\u548C\u8D26\u53F7\u6001\u5224\u65AD\u5DF2\u7ECF\u6536\u53E3\u5230\u5171\u4EAB\u5C42\uFF0C\u65E7\u524D\u7AEF\u53EA\u4FDD\u7559\u9875\u9762\u4E0A\u4E0B\u6587\u58F3\u3002",
    owner: "spec011"
  },
  {
    feature_key: "shared-household-runtime",
    legacy_entry: "apps/user-web/src/state/household.tsx",
    new_entry: "packages/user-core/src/state/household.ts",
    status: "ready",
    blocking_reason: "\u5BB6\u5EAD\u6458\u8981\u3001\u6301\u4E45\u5316 key \u548C\u8BFB\u5199 helper \u5DF2\u8FDB\u5165\u5171\u4EAB\u5C42\uFF0C\u65E7\u524D\u7AEF\u901A\u8FC7\u517C\u5BB9\u6865\u63A5\u6D88\u8D39\u3002",
    owner: "spec011"
  },
  {
    feature_key: "shared-setup-runtime",
    legacy_entry: "apps/user-web/src/state/setup.tsx",
    new_entry: "packages/user-core/src/state/setup.ts",
    status: "ready",
    blocking_reason: "setup status \u8BFB\u53D6 helper \u5DF2\u6536\u53E3\u5230\u5171\u4EAB\u5C42\uFF0C\u65E7\u524D\u7AEF\u517C\u5BB9\u5C42\u53EA\u4FDD\u7559\u6700\u8584\u6865\u63A5\u3002",
    owner: "spec011"
  },
  {
    feature_key: "shared-theme-preferences",
    legacy_entry: "apps/user-web/src/theme/ThemeProvider.tsx",
    new_entry: "packages/user-core/src/state/theme.ts",
    status: "ready",
    blocking_reason: "\u4E3B\u9898 ID\u3001\u9ED8\u8BA4\u503C\u548C\u6301\u4E45\u5316\u89C4\u5219\u5DF2\u5171\u4EAB\uFF0C\u65E7\u524D\u7AEF\u4FDD\u7559\u81EA\u5DF1\u7684\u89C6\u89C9 token \u4F46\u4E0D\u518D\u91CD\u590D\u7EF4\u62A4\u504F\u597D\u89C4\u5219\u3002",
    owner: "spec011"
  },
  {
    feature_key: "shared-locale-preferences",
    legacy_entry: "apps/user-web/src/i18n/localeRegistry.ts",
    new_entry: "packages/user-core/src/state/locale.ts",
    status: "ready",
    blocking_reason: "\u8BED\u8A00\u76EE\u5F55\u89E3\u6790\u3001fallback \u548C\u5B58\u50A8 key \u5DF2\u5171\u4EAB\uFF0C\u65E7\u524D\u7AEF\u4FDD\u7559\u6D88\u606F\u5B57\u5178\u4F46\u4E0D\u518D\u590D\u5236\u540C\u4E00\u5957 locale \u89C4\u5219\u3002",
    owner: "spec011"
  },
  {
    feature_key: "shared-realtime-protocol",
    legacy_entry: "apps/user-web/src/lib/realtime.ts",
    new_entry: "packages/user-platform/src/realtime/index.ts",
    status: "ready",
    blocking_reason: "\u5B9E\u65F6\u534F\u8BAE\u6821\u9A8C\u3001URL \u6784\u9020\u548C\u6D4F\u89C8\u5668 websocket client \u5DF2\u8FDB\u5165\u5E73\u53F0\u9002\u914D\u5C42\uFF0C\u65E7\u524D\u7AEF\u53EA\u4FDD\u7559\u8584\u5305\u88C5\u3002",
    owner: "spec011"
  },
  {
    feature_key: "shared-family-settings-api",
    legacy_entry: "apps/user-web/src/lib/api.ts",
    new_entry: "packages/user-core/src/api/create-api-client.ts",
    status: "ready",
    blocking_reason: "\u9996\u9875\u3001\u5BB6\u5EAD\u3001\u8BBE\u7F6E\u8FC1\u79FB\u4F1A\u7528\u5230\u7684\u6838\u5FC3 API \u548C\u9886\u57DF\u6A21\u578B\u5DF2\u7ECF\u62BD\u5230\u5171\u4EAB client\uFF0C\u65E7\u524D\u7AEF\u672C\u5730 API \u53EA\u4FDD\u7559\u9AD8\u9636\u80FD\u529B\u6269\u5C55\u3002",
    owner: "spec011"
  },
  {
    feature_key: "login",
    legacy_entry: "apps/user-web/src/pages/LoginPage.tsx",
    new_entry: "apps/user-app/src/pages/login/index.tsx",
    status: "ready",
    blocking_reason: "\u65E7 login \u9875\u7684\u5E03\u5C40\u3001\u6587\u6848\u3001\u4E3B\u9898/\u8BED\u8A00\u5207\u6362\u548C\u767B\u5F55\u4EA4\u4E92\u5DF2\u7ECF\u6B63\u5F0F\u8FC1\u5230 user-app\uff0c\u5B9E\u9645\u767B\u5F55\u7EE7\u7EED\u8D70\u5171\u4EAB\u9274\u6743 client \u548C\u542F\u52A8\u6458\u8981\u5206\u6D41\u3002",
    owner: "spec011"
  },
  {
    feature_key: "setup-wizard",
    legacy_entry: "apps/user-web/src/pages/SetupWizardPage.tsx",
    new_entry: "apps/user-app/src/pages/setup/index.tsx",
    status: "ready",
    blocking_reason: "\u521D\u59CB\u5316\u5411\u5BFC\u56DB\u6B65\u5DF2\u8FC1\u5165 user-app\uFF1A\u5171\u4EAB\u5C42\u5DF2\u8865\u9F50 provider / route / butler bootstrap \u6A21\u578B\u4E0E API\uFF0C\u9875\u9762\u5DF2\u63A5\u5165\u5F53\u524D\u5BB6\u5EAD\u4E0A\u4E0B\u6587\u3001\u6700\u5C0F AI \u4E3B\u94FE\u914D\u7F6E\u3001\u9996\u4F4D\u7BA1\u5BB6\u5B9E\u65F6\u5F15\u5BFC\u4E0E\u5237\u65B0\u4E00\u81F4\u6027\u3002",
    owner: "spec011"
  },
  {
    feature_key: "home",
    legacy_entry: "apps/user-web/src/pages/HomePage.tsx",
    new_entry: "apps/user-app/src/pages/home/index.tsx",
    status: "ready",
    blocking_reason: "\u5BB6\u5EAD\u6A21\u5F0F\u3001\u6307\u6807\u3001\u623F\u95F4\u3001\u6210\u5458\u3001\u63D0\u9192\u4E0E\u5FEB\u6377\u5165\u53E3\u90FD\u5DF2\u843D\u5230\u65B0\u9996\u9875\u3002",
    owner: "spec011"
  },
  {
    feature_key: "home-dashboard-shared-models",
    legacy_entry: "apps/user-web/src/pages/HomePage.tsx",
    new_entry: "packages/user-core/src/api/create-api-client.ts",
    status: "ready",
    blocking_reason: "\u9996\u9875\u4EEA\u8868\u76D8\u4F9D\u8D56\u7684 `ContextOverviewRead`\u3001\u63D0\u9192\u603B\u89C8\u548C\u8BBE\u5907/\u6210\u5458/\u623F\u95F4\u6A21\u578B\u5DF2\u5171\u4EAB\uFF0C\u540E\u7EED\u53EA\u5DEE\u9875\u9762\u88C5\u914D\u3002",
    owner: "spec011"
  },
  {
    feature_key: "family",
    legacy_entry: "apps/user-web/src/pages/FamilyPage.tsx",
    new_entry: "apps/user-app/src/pages/family/index.tsx",
    status: "ready",
    blocking_reason: "\u5BB6\u5EAD\u8D44\u6599\u3001\u623F\u95F4\u3001\u6210\u5458\u548C\u5173\u7CFB\u7684\u6838\u5FC3\u8BFB\u5199\u94FE\u8DEF\u5DF2\u8FC1\u5165\u65B0\u9875\u9762\u3002",
    owner: "spec011"
  },
  {
    feature_key: "family-domain-models",
    legacy_entry: "apps/user-web/src/pages/FamilyPage.tsx",
    new_entry: "packages/user-core/src/domain/types.ts",
    status: "ready",
    blocking_reason: "\u5BB6\u5EAD\u9875\u4F9D\u8D56\u7684\u623F\u95F4\u3001\u6210\u5458\u3001\u5173\u7CFB\u3001\u504F\u597D\u548C\u4E0A\u4E0B\u6587\u8BFB\u6A21\u578B\u5DF2\u8FDB\u5165\u5171\u4EAB\u5C42\u3002",
    owner: "spec011"
  },
  {
    feature_key: "assistant",
    legacy_entry: "apps/user-web/src/pages/AssistantPage.tsx",
    new_entry: "apps/user-app/src/pages/assistant/index.tsx",
    status: "ready",
    blocking_reason: "\u52A9\u624B\u4E3B\u94FE\u5DF2\u8FC1\u5165 user-app\uFF1A\u5171\u4EAB\u5C42\u5DF2\u8865\u9F50 agent / \u4F1A\u8BDD / \u6D88\u606F / \u52A8\u4F5C / \u5EFA\u8BAE\u6A21\u578B\u4E0E API\uFF0C\u9875\u9762\u5DF2\u63A5\u5165\u5B9E\u65F6\u4E0E HTTP \u53CC\u901A\u9053\u56DE\u590D\u3002",
    owner: "spec011"
  },
  {
    feature_key: "memories",
    legacy_entry: "apps/user-web/src/pages/MemoriesPage.tsx",
    new_entry: "apps/user-app/src/pages/memories/index.tsx",
    status: "ready",
    blocking_reason: "\u8BB0\u5FC6\u4E3B\u94FE\u5DF2\u8FC1\u5165 user-app\uFF0C\u5217\u8868\u3001\u641C\u7D22\u5206\u7C7B\u3001\u8BE6\u60C5\u3001\u7EA0\u9519/\u5931\u6548/\u5220\u9664\u4E0E\u4FEE\u8BA2\u5386\u53F2\u90FD\u76F4\u63A5\u6D88\u8D39\u5171\u4EAB\u8BB0\u5FC6\u6A21\u578B\u548C API\u3002",
    owner: "spec011"
  },
  {
    feature_key: "settings",
    legacy_entry: "apps/user-web/src/pages/SettingsPage.tsx",
    new_entry: "apps/user-app/src/pages/settings/index.tsx",
    status: "ready",
    blocking_reason: "\u8FD9\u91CC\u53EA\u4EE3\u8868\u57FA\u7840\u504F\u597D\u3001\u8FD0\u884C\u6A21\u5F0F\u3001\u670D\u52A1\u5F00\u5173\u548C\u514D\u6253\u6270\u65F6\u6BB5\u5DF2\u8FC1\u5165 H5\uFF1BAI\u3001\u96C6\u6210\u548C\u901A\u8BAF\u63A5\u5165\u8FD9\u4E9B\u8BBE\u7F6E\u5B50\u5165\u53E3\u8981\u5355\u72EC\u8BB0\u8D26\uFF0C\u4E0D\u80FD\u88AB\u8FD9\u4E00\u9879\u63A9\u76D6\u3002",
    owner: "spec011"
  },
  {
    feature_key: "settings-theme-language",
    legacy_entry: "apps/user-web/src/pages/SettingsPage.tsx",
    new_entry: "apps/user-app/src/pages/settings/index.tsx",
    status: "ready",
    blocking_reason: "\u4E3B\u9898\u4E0E\u8BED\u8A00\u504F\u597D\u5DF2\u7ECF\u5728\u65B0\u5E94\u7528\u8BBE\u7F6E\u9875\u843D\u5730\uFF0C\u5E76\u76F4\u63A5\u4F7F\u7528\u5171\u4EAB\u504F\u597D\u6A21\u578B\u3002",
    owner: "spec011"
  },
  {
    feature_key: "settings-ai",
    legacy_entry: "apps/user-web/src/pages/SettingsAiPage.tsx",
    new_entry: "apps/user-app/src/pages/settings/ai/index.tsx",
    status: "ready",
    blocking_reason: "\u6B63\u5F0F\u7684 settings/ai \u957F\u671F\u5165\u53E3\u5DF2\u7ECF\u843D\u5730\uFF0C\u8986\u76D6 provider \u7BA1\u7406\u3001\u80FD\u529B\u8DEF\u7531\u3001\u9996\u4F4D\u7BA1\u5BB6\u8865\u5EFA\u4E0E Agent \u914D\u7F6E\u4E2D\u5FC3\uFF0C\u5E76\u590D\u7528\u5171\u4EAB AI provider / route / agent API\u3002",
    owner: "spec011"
  },
  {
    feature_key: "settings-notifications",
    legacy_entry: "apps/user-web/src/pages/SettingsPage.tsx",
    new_entry: "apps/user-app/src/pages/settings/index.tsx",
    status: "in_progress",
    blocking_reason: "H5 \u5DF2\u8986\u76D6\u514D\u6253\u6270\u5F00\u5173\u548C\u65F6\u6BB5\u8FD9\u4E9B\u771F\u5B9E\u5B57\u6BB5\uFF0C\u4F46\u6CA1\u6709\u72EC\u7ACB\u901A\u77E5\u9875\uFF1B\u65E7\u9875\u91CC\u7684\u901A\u77E5\u65B9\u5F0F\u548C\u8303\u56F4\u672C\u8EAB\u4E5F\u4E3B\u8981\u662F\u5360\u4F4D\u8BF4\u660E\u3002",
    owner: "spec011"
  },
  {
    feature_key: "settings-accessibility",
    legacy_entry: "apps/user-web/src/pages/SettingsPage.tsx",
    new_entry: "apps/user-app/src/pages/settings/index.tsx",
    status: "ready",
    blocking_reason: "\u957F\u8F88\u53CB\u597D\u6A21\u5F0F\u672C\u8D28\u4E0A\u662F\u4E3B\u9898\u5207\u6362\uFF0CH5 \u8BBE\u7F6E\u9875\u5DF2\u7ECF\u5177\u5907\u5BF9\u5E94\u80FD\u529B\uFF1B\u73B0\u5728\u7F3A\u7684\u662F\u5355\u72EC\u5165\u53E3\uFF0C\u4E0D\u662F\u5E95\u5C42\u5B9E\u73B0\u3002",
    owner: "spec011"
  },
  {
    feature_key: "settings-integrations",
    legacy_entry: "apps/user-web/src/pages/SettingsPage.tsx",
    new_entry: "apps/user-app/src/pages/settings/integrations/index.tsx",
    status: "ready",
    blocking_reason: "settings/integrations \u5DF2\u843D\u5730\u5230 user-app\uFF0C\u8986\u76D6 Home Assistant \u914D\u7F6E\u3001\u8BBE\u5907\u540C\u6B65\u3001\u623F\u95F4\u540C\u6B65\u4E0E\u8BED\u97F3\u7EC8\u7AEF\u53D1\u73B0/\u8BA4\u9886\uFF0C\u53EA\u6D88\u8D39\u5DF2\u6709\u540E\u7AEF\u80FD\u529B\u5E76\u4FDD\u7559\u53EF\u8FD0\u884C\u8FB9\u754C\u3002",
    owner: "spec011"
  },
  {
    feature_key: "settings-channel-access",
    legacy_entry: "apps/user-web/src/pages/SettingsChannelAccessPage.tsx",
    new_entry: "apps/user-app/src/pages/settings/channel-access/index.tsx",
    status: "ready",
    blocking_reason: "settings/channel-access \u5DF2\u843D\u5730\u5230 user-app\uFF0C\u8986\u76D6\u5E73\u53F0\u8D26\u53F7\u5217\u8868\u3001\u65B0\u589E/\u7F16\u8F91\u3001\u72B6\u6001\u63A2\u6D4B\u3001\u542F\u7528/\u505C\u7528\u3001\u5931\u8D25\u8BB0\u5F55\u4E0E\u6210\u5458\u7ED1\u5B9A\uFF0C\u5E76\u4FDD\u6301\u5BB6\u5EAD\u5207\u6362\u540E\u7684\u5237\u65B0\u4E00\u81F4\u6027\u3002",
    owner: "spec011"
  },
  {
    feature_key: "plugins",
    legacy_entry: "apps/user-web/src/pages/SettingsPluginsPage.tsx",
    new_entry: "apps/user-app/src/pages/plugins/index.tsx",
    status: "ready",
    blocking_reason: "\u63D2\u4EF6\u4E3B\u94FE\u5DF2\u8FC1\u5165 user-app\uFF1A\u5171\u4EAB\u5C42\u5DF2\u8865\u9F50\u63D2\u4EF6\u6CE8\u518C\u8868 / \u6302\u8F7D / \u542F\u505C\u72B6\u6001 / \u6700\u8FD1\u4EFB\u52A1\u6A21\u578B\u4E0E API\uFF0C\u9875\u9762\u5DF2\u63A5\u5165\u5217\u8868\u3001\u8BE6\u60C5\u3001\u6302\u8F7D\u3001\u542F\u7528 / \u7981\u7528\u3001\u5220\u9664\u6302\u8F7D\u4E0E\u5BB6\u5EAD\u5207\u6362\u5237\u65B0\u3002",
    owner: "spec011"
  }
];
var userWebParityRegistry = {
  generatedAt: "2026-03-15",
  freezeRule: "\u8FC1\u79FB\u671F user-web \u53EA\u5141\u8BB8\u963B\u65AD\u7EA7\u7F3A\u9677\u4FEE\u590D\u548C\u8FC1\u79FB\u6865\u63A5\uFF0C\u4E0D\u518D\u627F\u63A5\u6B63\u5F0F\u65B0\u529F\u80FD\u3002",
  items: userWebPageParity
};
export {
  countParityItems,
  userWebParityRegistry
};

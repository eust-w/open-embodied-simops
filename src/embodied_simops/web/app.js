const DEFAULT_LANG = "zh";

const state = {
  catalog: null,
  configPath: null,
  teleopSessionId: null,
  selectedDatasets: new Set(),
  inspectedDatasetPath: null,
  lang: localStorage.getItem("simops.language") || DEFAULT_LANG,
  health: "checking",
  activePage: "generate",
  runtimeStatus: null,
  runtimeDependencies: null,
  runs: [],
  artifacts: [],
  datasets: [],
  assetLibrary: null,
  models: [],
  deployments: [],
  stages: [],
  generationJobs: [],
  threeModule: null,
  assetPreviewViewer: null,
  simulationPreviewViewer: null,
  assetPreviewPath: null,
  simViewMode: "render",
  simFrameStreamActive: false,
  simFrameStreamSessionId: null,
  nativeSimulatorUi: null,
};

const I18N = {
  zh: {
    pageTitle: "Open Embodied SimOps",
    checking: "检查中",
    apiOnline: "API 在线",
    offline: "离线",
    navGenerate: "场景/资产生成",
    navAssets: "场景/资产管理",
    navSimulation: "仿真控制台",
    navDatasets: "数据集",
    navTraining: "训练",
    navDeployment: "部署",
    stateDir: "状态目录",
    refresh: "刷新",
    generateTitle: "场景/资产生成",
    generateWorkbenchTitle: "生成工作台",
    generationReady: "选择生成器后生成真实场景/资产产物",
    generator: "生成器",
    generationName: "生成名称",
    generationCount: "生成数量",
    generationFormat: "输出格式",
    generateScene: "生成场景",
    generateAsset: "生成资产",
    generatePackage: "生成场景资产包",
    generationJobs: "生成记录",
    generationJobsSubtitle: "每个生成产物都有来源、版本、license 和 hash",
    noGenerationJobs: "暂无生成记录",
    generationSucceeded: "生成成功",
    generationGeneratorReady: "{label}：{status}",
    generationGeneratorNeeds: "{label}：{status}，需要 {env}",
    taskConfigTitle: "任务配置",
    assetManageTitle: "场景/资产管理",
    assetManageSubtitle: "目录状态来自 API 注册表，未接入的开源组件会明确标记为未配置",
    generatedPackages: "真实生成包",
    generatedPackagesSubtitle: "来自状态目录下 package_manifest.json 的场景和资产",
    deploymentTitle: "部署",
    deploymentSubtitle: "查看运行记录、阶段、产物和导出的 ROS 2 / LeRobot rollout 接口",
    deploymentInterfaces: "部署接口",
    builderTitle: "SimOps 构建器",
    noConfigGenerated: "尚未生成配置",
    generateConfig: "生成配置",
    validate: "校验",
    taskName: "任务名称",
    simulator: "仿真器",
    robot: "机器人本体",
    scene: "场景",
    task: "任务",
    sensors: "传感器",
    demoEpisodes: "演示条数",
    seed: "随机种子",
    runtimeEnvironment: "运行环境",
    libraryTitle: "场景与资产库",
    librarySubtitle: "目录状态来自 API 注册表",
    scenes: "场景",
    assets: "资产",
    robots: "机器人",
    simulationTitle: "仿真控制台",
    simulationViewport: "仿真视窗",
    noSession: "未启动会话",
    teleopBridge: "遥操作桥接",
    createSimulationSession: "创建仿真会话",
    closeSimulationSession: "关闭会话",
    simulationApiTitle: "仿真 API",
    latestFrame: "读取最新画面",
    createPlayback: "创建回放",
    connectFrameStream: "连接实时帧流",
    liveFrameStream: "真实帧流",
    frameStreamConnected: "实时真实帧流已连接",
    nativeSimulatorUi: "原生仿真器 UI",
    openNativeUi: "原生 UI",
    nativeUiUnavailable: "原生 UI 未配置，使用内置真实渲染流",
    nativeUiEmbedded: "原生 UI 已嵌入",
    renderFrame: "真实渲染帧",
    renderFrameWaiting: "等待会话帧",
    renderFrameUpdated: "渲染帧已更新",
    realRenderView: "真实帧",
    state3dView: "状态 3D",
    noApiResult: "暂无 API 响应",
    simulationApiReady: "交互式仿真 API",
    collectTrajectories: "采集轨迹",
    runPipeline: "运行完整闭环",
    openGripper: "打开",
    closeGripper: "闭合",
    lift: "抬升",
    lower: "下降",
    online3dPreview: "在线 3D 预览",
    fullscreen: "全屏",
    refresh3dPreview: "刷新 3D 预览",
    preview3d: "3D 预览",
    previewLoaded: "预览已加载",
    noGeneratedPackageSelected: "未选择生成包",
    datasetsTitle: "数据集",
    noDatasetSelected: "未选择数据集",
    mergeSelected: "合并选中",
    datasetArtifacts: "数据集产物",
    conversionTarget: "转换目标",
    datasetPreview: "数据集可视化",
    dataFormat: "数据格式",
    mergeOutputPath: "合并输出路径",
    trainingTitle: "训练",
    trainingSubtitle: "使用任务配置中选中或生成的 LeRobot 数据集",
    startTraining: "启动真实训练闭环",
    modelArtifacts: "模型与训练产物",
    modelArtifactsSubtitle: "来自真实训练运行目录和 provenance ledger",
    policy: "策略模型",
    trainSteps: "训练步数",
    batchSize: "批大小",
    datasetRepoId: "数据集 repo id",
    evalEpisodes: "评测条数",
    minSuccess: "最低成功率",
    runsDeployment: "运行与部署",
    noActiveRun: "没有正在运行的任务",
    runs: "运行记录",
    stages: "阶段",
    artifacts: "产物",
    noStages: "选择一次运行后查看阶段",
    noRuns: "当前状态目录没有运行记录",
    noArtifacts: "暂无产物",
    noModels: "暂无模型产物",
    noDeployments: "暂无部署接口",
    noLerobotDatasets: "暂无 LeRobot 数据集",
    configGenerated: "配置已生成并通过校验",
    configValid: "配置有效",
    selectAtLeastTwoDatasets: "至少选择两个数据集",
    mergeStatus: "合并",
    noTeleopSession: "没有遥操作会话",
    sessionStarted: "会话已启动",
    sessionClosed: "会话已关闭",
    sentAction: "已发送",
    datasetSelected: "{count} 个数据集已选择",
    collectStarted: "已启动真实轨迹采集任务",
    runtimeOverrides: "运行命令覆盖",
    runtimeDependencies: "平台依赖",
    dependencyChecking: "等待检查",
    startBridgeService: "启动仿真桥接",
    installingRuntime: "正在安装/启动真实运行组件",
    dependencyInstallDone: "运行组件已安装/启动",
    runtimeReady: "运行环境可用",
    runtimeNotReady: "运行环境未就绪",
    executableReady: "命令可执行",
    executableMissing: "命令缺失",
    teleopBridgeMissing:
      "真实交互式仿真桥接未运行；请启动平台托管的 simops-bridge.service",
    motrixsimBridgeMissing:
      "MotrixSim 真实交互桥尚未接入；当前支持 MotrixSim 包导入、真实步进校验和 3D 预览",
    mergeCommandMissing: "未配置 SIMOPS_LEROBOT_PYTHON；无法运行内置 LeRobot 合并",
  },
  en: {
    pageTitle: "Open Embodied SimOps",
    checking: "checking",
    apiOnline: "api online",
    offline: "offline",
    navGenerate: "Scene/Asset Generation",
    navAssets: "Scene/Asset Management",
    navSimulation: "Simulation Console",
    navDatasets: "Datasets",
    navTraining: "Training",
    navDeployment: "Deploy",
    stateDir: "State dir",
    refresh: "Refresh",
    generateTitle: "Scene/Asset Generation",
    generateWorkbenchTitle: "Generation Workbench",
    generationReady: "Choose a generator to produce real scene/asset artifacts",
    generator: "Generator",
    generationName: "Generation name",
    generationCount: "Count",
    generationFormat: "Output format",
    generateScene: "Generate Scene",
    generateAsset: "Generate Asset",
    generatePackage: "Generate Scene/Asset Package",
    generationJobs: "Generation Jobs",
    generationJobsSubtitle: "Every generated artifact includes source, version, license, and hash",
    noGenerationJobs: "No generation jobs",
    generationSucceeded: "Generation succeeded",
    generationGeneratorReady: "{label}: {status}",
    generationGeneratorNeeds: "{label}: {status}, requires {env}",
    taskConfigTitle: "Task Config",
    assetManageTitle: "Scene/Asset Management",
    assetManageSubtitle: "Catalog status comes from the API registry; unwired open-source components are marked explicitly",
    generatedPackages: "Real Generated Packages",
    generatedPackagesSubtitle: "Scenes and assets read from package_manifest.json in the state directory",
    deploymentTitle: "Deployment",
    deploymentSubtitle: "Inspect runs, stages, artifacts, and exported ROS 2 / LeRobot rollout interfaces",
    deploymentInterfaces: "Deployment interfaces",
    builderTitle: "SimOps Builder",
    noConfigGenerated: "No config generated",
    generateConfig: "Generate Config",
    validate: "Validate",
    taskName: "Task name",
    simulator: "Simulator",
    robot: "Robot",
    scene: "Scene",
    task: "Task",
    sensors: "Sensors",
    demoEpisodes: "Demo episodes",
    seed: "Seed",
    runtimeEnvironment: "Runtime environment",
    libraryTitle: "Scene & Asset Library",
    librarySubtitle: "Catalog status comes from the API registry",
    scenes: "Scenes",
    assets: "Assets",
    robots: "Robots",
    simulationTitle: "Simulation Console",
    simulationViewport: "Simulation viewport",
    noSession: "No session",
    teleopBridge: "Teleop bridge",
    createSimulationSession: "Create Simulation Session",
    closeSimulationSession: "Close Session",
    simulationApiTitle: "Simulation API",
    latestFrame: "Latest Frame",
    createPlayback: "Create Playback",
    connectFrameStream: "Connect Live Frames",
    liveFrameStream: "Live frame stream",
    frameStreamConnected: "Live rendered frame stream connected",
    nativeSimulatorUi: "Native Simulator UI",
    openNativeUi: "Native UI",
    nativeUiUnavailable: "Native UI is not configured; using the built-in real render stream",
    nativeUiEmbedded: "Native UI embedded",
    renderFrame: "Rendered frame",
    renderFrameWaiting: "Waiting for session frame",
    renderFrameUpdated: "Rendered frame updated",
    realRenderView: "Rendered Frame",
    state3dView: "State 3D",
    noApiResult: "No API response",
    simulationApiReady: "Interactive simulation API",
    collectTrajectories: "Collect Trajectories",
    runPipeline: "Run Full Loop",
    openGripper: "Open",
    closeGripper: "Close",
    lift: "Lift",
    lower: "Lower",
    online3dPreview: "Online 3D Preview",
    fullscreen: "Fullscreen",
    refresh3dPreview: "Refresh 3D Preview",
    preview3d: "3D Preview",
    previewLoaded: "Preview loaded",
    noGeneratedPackageSelected: "No generated package selected",
    datasetsTitle: "Datasets",
    noDatasetSelected: "No dataset selected",
    mergeSelected: "Merge Selected",
    datasetArtifacts: "Dataset artifacts",
    conversionTarget: "Conversion target",
    datasetPreview: "Dataset preview",
    dataFormat: "Data format",
    mergeOutputPath: "Merge output path",
    trainingTitle: "Training",
    trainingSubtitle: "Uses selected/generated LeRobot dataset in the task config",
    startTraining: "Start Real Training Loop",
    modelArtifacts: "Models & training artifacts",
    modelArtifactsSubtitle: "Read from real training run directories and provenance ledger",
    policy: "Policy",
    trainSteps: "Train steps",
    batchSize: "Batch size",
    datasetRepoId: "Dataset repo id",
    evalEpisodes: "Eval episodes",
    minSuccess: "Min success",
    runsDeployment: "Runs & Deployment",
    noActiveRun: "No active run",
    runs: "Runs",
    stages: "Stages",
    artifacts: "Artifacts",
    noStages: "Select a run to inspect stages",
    noRuns: "No runs in this state dir",
    noArtifacts: "No artifacts",
    noModels: "No model artifacts",
    noDeployments: "No deployment interfaces",
    noLerobotDatasets: "No LeRobot datasets",
    configGenerated: "Config generated and validated",
    configValid: "Config is valid",
    selectAtLeastTwoDatasets: "Select at least two datasets",
    mergeStatus: "Merge",
    noTeleopSession: "No teleop session",
    sessionStarted: "Session started",
    sessionClosed: "Session closed",
    sentAction: "Sent",
    datasetSelected: "{count} dataset(s) selected",
    collectStarted: "Started a real trajectory collection run",
    runtimeOverrides: "Runtime command overrides",
    runtimeDependencies: "Platform dependencies",
    dependencyChecking: "Waiting for check",
    startBridgeService: "Start Simulation Bridge",
    installingRuntime: "Installing/starting real runtime components",
    dependencyInstallDone: "Runtime components installed/started",
    runtimeReady: "Runtime ready",
    runtimeNotReady: "Runtime not ready",
    executableReady: "Executable ready",
    executableMissing: "Executable missing",
    teleopBridgeMissing:
      "The real interactive simulation bridge is not running; start the managed simops-bridge.service",
    motrixsimBridgeMissing:
      "MotrixSim real interactive bridge is not wired yet; package import, real step validation, and 3D preview are supported",
    mergeCommandMissing:
      "SIMOPS_LEROBOT_PYTHON is not configured; cannot run built-in LeRobot merge",
  },
};

const STATUS_LABELS = {
  zh: {
    available: "可用",
    succeeded: "成功",
    running: "运行中",
    failed: "失败",
    unconfigured: "未配置",
    config_available: "配置可用",
    deployment_target: "部署目标",
    requires_robocasa: "需 RoboCasa",
    requires_asset_source: "需资产源",
    requires_renderer: "需渲染器",
    requires_SIMOPS_LEROBOT_PYTHON: "需 LeRobot Python",
    not_configured: "未配置",
    compatible_export_planned: "兼容导出规划中",
    available_if_installed: "已安装则可用",
  },
  en: {
    available: "available",
    succeeded: "succeeded",
    running: "running",
    failed: "failed",
    unconfigured: "unconfigured",
    config_available: "config available",
    deployment_target: "deployment target",
    requires_robocasa: "requires RoboCasa",
    requires_asset_source: "requires asset source",
    requires_renderer: "requires renderer",
    requires_SIMOPS_LEROBOT_PYTHON: "requires LeRobot Python",
    not_configured: "not configured",
    compatible_export_planned: "compatible export planned",
    available_if_installed: "available if installed",
  },
};

const ROLE_LABELS = {
  zh: {
    trajectory_dataset: "轨迹数据",
    trajectory_metadata: "轨迹元数据",
    lerobot_dataset: "LeRobot 数据集",
    training_run: "训练运行",
    model: "模型",
    model_manifest: "模型清单",
    evaluation_report: "评测报告",
    deployment_interface: "部署接口",
    scene_manifest: "场景清单",
    asset_manifest: "资产清单",
    motrix_scene_xml: "MotrixSim XML",
    motrix_validation: "MotrixSim 校验",
  },
  en: {
    trajectory_dataset: "trajectory dataset",
    trajectory_metadata: "trajectory metadata",
    lerobot_dataset: "LeRobot dataset",
    training_run: "training run",
    model: "model",
    model_manifest: "model manifest",
    evaluation_report: "evaluation report",
    deployment_interface: "deployment interface",
    scene_manifest: "scene manifest",
    asset_manifest: "asset manifest",
    motrix_scene_xml: "MotrixSim XML",
    motrix_validation: "MotrixSim validation",
  },
};

const $ = (id) => document.getElementById(id);

const ROUTE_ALIASES = {
  configure: "generate",
  library: "assets",
  data: "datasets",
  train: "training",
  deploy: "deployment",
};

function currentPageFromHash() {
  const raw = (window.location.hash || "#generate").slice(1);
  return ROUTE_ALIASES[raw] || raw || "generate";
}

function syncRoute() {
  const page = document.getElementById(currentPageFromHash()) ? currentPageFromHash() : "generate";
  state.activePage = page;
  document.querySelectorAll(".page").forEach((node) => {
    node.classList.toggle("active-page", node.id === page);
  });
  document.querySelectorAll("[data-page-link]").forEach((node) => {
    node.classList.toggle("active", node.dataset.pageLink === page);
  });
  if (window.location.hash !== `#${page}`) {
    history.replaceState(null, "", `#${page}`);
  }
}

function t(key, values = {}) {
  const template = I18N[state.lang]?.[key] || I18N[DEFAULT_LANG][key] || key;
  return Object.entries(values).reduce((text, [name, value]) => text.replace(`{${name}}`, value), template);
}

function statusLabel(status = "available") {
  return STATUS_LABELS[state.lang]?.[status] || status;
}

function roleLabel(role) {
  return ROLE_LABELS[state.lang]?.[role] || role;
}

function itemLabel(item) {
  if (state.lang === "zh") return item.label_zh || item.label || item.id;
  return item.label || item.id;
}

function applyTranslations() {
  document.documentElement.lang = state.lang === "zh" ? "zh-CN" : "en";
  document.title = t("pageTitle");
  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = t(node.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-aria]").forEach((node) => {
    node.setAttribute("aria-label", t(node.dataset.i18nAria));
  });
  document.querySelectorAll("[data-lang]").forEach((button) => {
    button.classList.toggle("active", button.dataset.lang === state.lang);
  });

  syncRoute();
  renderHealthStatus();
  if (!state.configPath) $("configStatus").textContent = t("noConfigGenerated");
  if (!state.teleopSessionId && state.catalog) renderTeleopStatus();
  renderSimulationApiStatus();
  if (state.selectedDatasets.size === 0) $("datasetStatus").textContent = t("noDatasetSelected");
  $("runStatus").textContent ||= t("noActiveRun");
  renderRuntimeStatus();
  renderRuntimeDependencies();
}

function setLanguage(lang) {
  state.lang = lang === "en" ? "en" : "zh";
  localStorage.setItem("simops.language", state.lang);
  applyTranslations();
  renderCatalog();
  renderRuns(state.runs);
  renderArtifacts(state.artifacts);
  renderDatasets(state.datasets);
  renderAssetLibrary();
  renderModels(state.models);
  renderDeployments(state.deployments);
  renderStages(state.stages);
  renderGenerationJobs(state.generationJobs);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) {
    const detail = payload?.detail || response.statusText;
    throw new Error(localizeError(typeof detail === "string" ? detail : JSON.stringify(detail)));
  }
  return payload;
}

async function loadThreeModule() {
  if (!state.threeModule) {
    state.threeModule = await import("/static/three_preview.js?v=20260609-3d1");
  }
  return state.threeModule;
}

async function ensurePreviewViewer(viewportId, statusId, stateKey) {
  const viewport = $(viewportId);
  if (!viewport) return null;
  if (!state[stateKey]) {
    const module = await loadThreeModule();
    state[stateKey] = new module.SimOpsThreePreview(viewport, {
      statusNode: statusId ? $(statusId) : null,
    });
  }
  return state[stateKey];
}

function setAppFullscreen(element, viewer, enabled) {
  if (!element) return;
  if (enabled && element.requestFullscreen) {
    element.requestFullscreen().then(() => window.setTimeout(() => viewer?.resize(), 80)).catch((error) => toast(error.message));
    return;
  }
  if (!enabled && document.fullscreenElement && document.exitFullscreen) {
    document.exitFullscreen().catch((error) => toast(error.message));
  }
  element.classList.toggle("app-fullscreen", enabled);
  document.body.classList.toggle("has-app-fullscreen", document.querySelectorAll(".app-fullscreen").length > 0);
  window.setTimeout(() => viewer?.resize(), 80);
}

function exitAppFullscreen() {
  document.querySelectorAll(".app-fullscreen").forEach((node) => node.classList.remove("app-fullscreen"));
  document.querySelectorAll("#simFullscreenToggle, #assetPreviewFullscreenToggle").forEach((node) => {
    node.checked = false;
  });
  document.body.classList.remove("has-app-fullscreen");
  window.setTimeout(() => {
    state.assetPreviewViewer?.resize();
    state.simulationPreviewViewer?.resize();
  }, 80);
}

function localizeError(message) {
  if (state.lang !== "zh") return message;
  if (message.includes("MotrixSim interactive bridge")) return t("motrixsimBridgeMissing");
  if (message.includes("SIMOPS_TELEOP_BRIDGE_URL")) return t("teleopBridgeMissing");
  if (message.includes("managed simulation bridge is not reachable")) return t("teleopBridgeMissing");
  if (message.includes("SIMOPS_LEROBOT_PYTHON")) return t("mergeCommandMissing");
  if (message.includes("refusing to fake") && message.includes("COMMAND")) {
    return message
      .replace(" is not configured; refusing to fake ", " 未配置；不会伪造 ")
      .replace(" generation", " 生成");
  }
  return message;
}

function toast(message) {
  const node = $("toast");
  node.textContent = message;
  node.classList.add("show");
  window.clearTimeout(node._timer);
  node._timer = window.setTimeout(() => node.classList.remove("show"), 3600);
}

function optionLabel(item) {
  return `${itemLabel(item)} · ${statusLabel(item.status || "available")}`;
}

function fillSelect(id, items) {
  const select = $(id);
  const previous = select.value;
  select.innerHTML = "";
  items.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.id;
    option.textContent = optionLabel(item);
    select.append(option);
  });
  if (items.some((item) => item.id === previous)) select.value = previous;
}

function setSelectValue(id, value) {
  const select = $(id);
  if (!select) return false;
  if (![...select.options].some((option) => option.value === value)) return false;
  select.value = value;
  return true;
}

function renderStatusList(id, items) {
  const container = $(id);
  container.innerHTML = "";
  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "item";
    row.innerHTML = `
      <strong>${itemLabel(item)}</strong>
      <span class="badge ${item.status || "available"}">${statusLabel(item.status)}</span>
      <small>${item.version || item.required_env?.join(", ") || item.id}</small>
    `;
    container.append(row);
  });
}

function renderAssets(items) {
  const checks = $("assetChecks");
  checks.innerHTML = "";
  items.forEach((item) => {
    const label = document.createElement("label");
    label.className = "check-pill";
    const checked = ["cube", "tabletop", "goal"].includes(item.id);
    label.innerHTML = `
      <input type="checkbox" value="${item.id}" ${checked ? "checked" : ""} />
      <span>${itemLabel(item)}</span>
      <span class="badge ${item.status || "available"}">${statusLabel(item.status)}</span>
    `;
    checks.append(label);
  });
}

function selectedAssets() {
  return [...document.querySelectorAll("#assetChecks input:checked")].map((node) => node.value);
}

function setSelectedAssets(ids) {
  const wanted = new Set(ids);
  document.querySelectorAll("#assetChecks input").forEach((node) => {
    node.checked = wanted.has(node.value);
  });
}

function envPayload() {
  const map = {
    SIMOPS_MANISKILL_MP_PYTHON: $("envManiskillPython").value.trim(),
    SIMOPS_LEROBOT_PYTHON: $("envLerobotPython").value.trim(),
    SIMOPS_LEROBOT_TRAIN: $("envLerobotTrain").value.trim(),
    SIMOPS_LEROBOT_RECORD: $("envLerobotRecord").value.trim(),
    SIMOPS_MOTRIXSIM_PYTHON: $("envMotrixsimPython")?.value.trim(),
    SIMOPS_MOTRIXSIM_DOCS: $("envMotrixsimDocs")?.value.trim(),
    SIMOPS_MOTRIXSIM_HOME: $("envMotrixsimHome")?.value.trim(),
    SIMOPS_MOTRIXSIM_PYTHONPATH: $("envMotrixsimPythonpath")?.value.trim(),
  };
  return Object.fromEntries(Object.entries(map).filter(([, value]) => value));
}

function applySimulatorDefaults(simulator) {
  if (!state.catalog) return;
  if (simulator === "motrixsim") {
    setSelectValue("sceneGenerator", "motrixsim_examples");
    setSelectValue("scene", "motrixsim_body");
    setSelectValue("robot", "motrix_body");
    setSelectValue("task", "MotrixSimStep");
    setSelectValue("dataFormat", "motrixsim_json");
    setSelectedAssets(["body", "cube", "sphere"]);
    if ($("generationName").value.includes("maniskill")) $("generationName").value = "ui-motrixsim-body-package";
    if ($("taskName").value.includes("maniskill")) $("taskName").value = "ui-motrixsim-step";
  } else if (simulator === "maniskill") {
    setSelectValue("sceneGenerator", "maniskill_tabletop");
    setSelectValue("scene", "maniskill_tabletop");
    setSelectValue("robot", "panda");
    setSelectValue("task", "PickCube-v1");
    setSelectValue("dataFormat", "lerobot");
    setSelectedAssets(["cube", "tabletop", "goal"]);
  }
  updateGenerationStatus();
}

function configPayload(mode = "full") {
  const domains = [...document.querySelectorAll("#assetChecks input:checked")]
    .map((node) => node.value)
    .includes("cube")
    ? ["object_pose", "camera_pose"]
    : ["camera_pose"];
  const baseName = $("taskName").value.trim() || "ui-maniskill-lerobot-pickcube";
  return {
    state_dir: $("stateDir").value.trim() || ".simops",
    name: mode === "collect" ? `${baseName}-collect` : baseName,
    simulator: $("simulator").value,
    robot: $("robot").value,
    scene: $("scene").value,
    assets: selectedAssets(),
    task: $("task").value,
    sensor_preset: $("sensorPreset").value,
    randomization_seed: Number($("seed").value),
    randomization_domains: domains,
    demo_episodes: Number($("demoEpisodes").value),
    data_format: $("dataFormat").value,
    policy_type: $("policyType").value,
    train_steps: Number($("trainSteps").value),
    batch_size: Number($("batchSize").value),
    eval_episodes: Number($("evalEpisodes").value),
    eval_max_steps: 120,
    min_success_rate: Number($("minSuccess").value),
    dataset_repo_id: $("datasetRepo").value.trim() || "simops/pickcube-real-ui",
    deployment_targets: ["ros2", "lerobot_rollout"],
    pipeline_mode: mode,
  };
}

function generationPayload(kind) {
  return {
    state_dir: $("stateDir").value.trim() || ".simops",
    name: $("generationName").value.trim() || "ui-maniskill-tabletop-package",
    generator: $("sceneGenerator").value,
    kind,
    scene: $("scene").value,
    assets: selectedAssets(),
    task: $("task").value,
    count: Number($("generationCount").value),
    seed: Number($("seed").value),
    output_format: $("generationFormat").value,
  };
}

async function generateSceneAsset(kind) {
  const payload = await api("/generation/jobs", {
    method: "POST",
    body: JSON.stringify(generationPayload(kind)),
  });
  $("generationStatus").textContent = `${t("generationSucceeded")}: ${payload.path}`;
  toast(`${t("generationSucceeded")}: ${payload.id}`);
  await loadGenerationJobs();
  await refresh();
  return payload;
}

function renderCatalog() {
  if (!state.catalog) return;
  const generationGenerators = state.catalog.scene_generators.filter((item) => {
    const external = Object.keys(state.catalog.generation?.external_commands || {});
    return state.catalog.generation?.built_in?.includes(item.id) || external.includes(item.id);
  });
  fillSelect("simulator", state.catalog.simulators);
  fillSelect("sceneGenerator", generationGenerators);
  fillSelect("robot", state.catalog.robots);
  fillSelect("scene", state.catalog.scene_generators);
  fillSelect("task", state.catalog.tasks);
  fillSelect("sensorPreset", state.catalog.sensors);
  fillSelect("dataFormat", state.catalog.data_formats);
  fillSelect("policyType", state.catalog.policies);
  renderAssets(state.catalog.assets);
  if (state.assetLibrary) renderAssetLibrary();
  else {
    renderStatusList("sceneList", state.catalog.scene_generators);
    renderStatusList("assetList", state.catalog.assets);
  }
  renderStatusList("robotList", state.catalog.robots);
  renderTeleopStatus();
  renderSimulationApiStatus();
  updateGenerationStatus();
}

function renderAssetLibrary() {
  if (!state.catalog) return;
  if (!state.assetLibrary) {
    renderStatusList("sceneList", state.catalog.scene_generators);
    renderStatusList("assetList", state.catalog.assets);
    return;
  }
  const scenes = state.assetLibrary.scenes?.length
    ? state.assetLibrary.scenes
    : state.catalog.scene_generators;
  const assets = state.assetLibrary.assets?.length ? state.assetLibrary.assets : state.catalog.assets;
  renderProductCards("sceneList", scenes, (item) => ({
    title: item.name || itemLabel(item),
    badge: item.status || "available",
    lines: [
      item.generator || item.id,
      item.path,
      item.sha256 ? `sha256 ${item.sha256}` : item.version || item.required_env?.join(", "),
      item.source?.license ? `${item.source.license} · ${item.source.version || ""}` : "",
    ],
  }));
  renderProductCards("assetList", assets, (item) => ({
    title: item.name || itemLabel(item),
    badge: item.status || "available",
    lines: [
      Array.isArray(item.assets) ? item.assets.join(", ") : item.id,
      item.path,
      item.sha256 ? `sha256 ${item.sha256}` : item.version || item.required_env?.join(", "),
      item.source?.license ? `${item.source.license} · ${item.source.version || ""}` : "",
    ],
  }));
  renderGeneratedPackageCards(state.assetLibrary.generated_packages || []);
  if (!state.assetPreviewPath && state.assetLibrary.generated_packages?.length) {
    previewGeneratedPackage(state.assetLibrary.generated_packages[0]).catch((error) => toast(error.message));
  }
}

function renderProductCards(id, items, projector, emptyText = t("noArtifacts")) {
  const container = $(id);
  if (!container) return;
  container.innerHTML = "";
  if (!items.length) {
    container.innerHTML = `<div class="artifact"><small>${emptyText}</small></div>`;
    return;
  }
  items.forEach((item) => {
    const projected = projector(item);
    const row = document.createElement("div");
    row.className = "artifact";
    row.innerHTML = `
      <strong>${projected.title}</strong>
      <span class="badge ${projected.badge}">${statusLabel(projected.badge)}</span>
      ${projected.lines.filter(Boolean).map((line) => `<small>${line}</small>`).join("")}
    `;
    container.append(row);
  });
}

function renderGeneratedPackageCards(items) {
  const container = $("generatedPackageList");
  if (!container) return;
  container.innerHTML = "";
  if (!items.length) {
    container.innerHTML = `<div class="artifact"><small>${t("noGenerationJobs")}</small></div>`;
    $("assetPreviewStatus").textContent = t("noGeneratedPackageSelected");
    $("assetPreviewMeta").textContent = t("noGeneratedPackageSelected");
    return;
  }
  items.forEach((item) => {
    const row = document.createElement("div");
    row.className = `artifact${state.assetPreviewPath === item.path ? " selected" : ""}`;
    row.innerHTML = `
      <strong>${item.name}</strong>
      <span class="badge ${item.status || "succeeded"}">${statusLabel(item.status || "succeeded")}</span>
      <small>${item.generator}</small>
      <small>${item.path}</small>
      <small>sha256 ${item.sha256}</small>
      <small>${(item.assets || []).join(", ")}</small>
      <button type="button" class="compact-button">${t("preview3d")}</button>
    `;
    row.querySelector("button").addEventListener("click", () => previewGeneratedPackage(item).catch((error) => toast(error.message)));
    container.append(row);
  });
}

async function previewGeneratedPackage(item) {
  const viewer = await ensurePreviewViewer("assetPreviewViewport", "assetPreviewStatus", "assetPreviewViewer");
  if (!viewer) return;
  const descriptor = await api(`/assets/preview?manifest_path=${encodeURIComponent(item.path)}`);
  state.assetPreviewPath = item.path;
  viewer.setScene(descriptor);
  $("assetPreviewStatus").textContent = `${t("previewLoaded")}: ${item.name}`;
  $("assetPreviewMeta").textContent = JSON.stringify(
    {
      name: descriptor.name,
      scene: descriptor.scene,
      task: descriptor.task,
      seed: descriptor.seed,
      source: descriptor.source,
      package_manifest: descriptor.package_manifest,
      generated_from: descriptor.generated_from,
      objects: (descriptor.objects || []).map((object) => ({
        id: object.id,
        geometry: object.geometry,
        position: object.position,
        source: object.source,
      })),
    },
    null,
    2,
  );
  renderGeneratedPackageCards(state.assetLibrary?.generated_packages || []);
}

function updateGenerationStatus() {
  if (!state.catalog || !$("sceneGenerator")) return;
  const selected = state.catalog.scene_generators.find((item) => item.id === $("sceneGenerator").value);
  if (!selected) return;
  const requiredEnv = selected.required_env?.join(", ");
  $("generationStatus").textContent =
    selected.status === "available"
      ? t("generationGeneratorReady", { label: itemLabel(selected), status: statusLabel(selected.status) })
      : t("generationGeneratorNeeds", {
          label: itemLabel(selected),
          status: statusLabel(selected.status),
          env: requiredEnv || "-",
        });
}

function renderTeleopStatus() {
  if (!state.catalog) {
    $("teleopStatus").textContent = t("noSession");
    return;
  }
  $("teleopStatus").textContent = `${t("teleopBridge")}: ${statusLabel(state.catalog.teleop.status)}`;
}

function renderSimulationApiStatus() {
  if (!$("simulationApiStatus")) return;
  const apiInfo = state.catalog?.simulation_api;
  if (!apiInfo) {
    $("simulationApiStatus").textContent = t("noSession");
    $("simulationApiList").innerHTML = "";
    $("simulationApiOutput").textContent ||= t("noApiResult");
    return;
  }
  const requiredEnv = apiInfo.required_env?.join(", ") || "";
  $("simulationApiStatus").textContent =
    `${t("simulationApiReady")}: ${statusLabel(apiInfo.status)}` + (requiredEnv ? ` · ${requiredEnv}` : "");
  $("simulationApiList").innerHTML = (apiInfo.public_endpoints || [])
    .map(
      (endpoint) => `
        <div class="api-row">
          <code>${endpoint}</code>
          <span class="badge ${apiInfo.status}">${statusLabel(apiInfo.status)}</span>
        </div>
      `,
    )
    .join("");
  const outputText = $("simulationApiOutput").textContent.trim();
  if (!outputText || outputText === I18N.zh.noApiResult || outputText === I18N.en.noApiResult) {
    $("simulationApiOutput").textContent = t("noApiResult");
  }
}

function renderRuntimeStatus() {
  const container = $("runtimeStatusList");
  if (!container) return;
  container.innerHTML = "";
  if (!state.runtimeStatus) {
    container.innerHTML = `<div class="status-card"><strong>${t("runtimeNotReady")}</strong></div>`;
    return;
  }
  const headline = document.createElement("div");
  headline.className = "status-card";
  headline.innerHTML = `
    <strong>${state.runtimeStatus.can_run_pipeline ? t("runtimeReady") : t("runtimeNotReady")}</strong>
    <span class="badge ${state.runtimeStatus.can_run_pipeline ? "available" : "failed"}">
      ${state.runtimeStatus.can_run_pipeline ? statusLabel("available") : statusLabel("failed")}
    </span>
    <small>${state.runtimeStatus.state_dir}</small>
  `;
  container.append(headline);

  state.runtimeStatus.checks.forEach((check) => {
    const row = document.createElement("div");
    row.className = "status-card";
    row.innerHTML = `
      <strong>${check.env}</strong>
      <span class="badge ${check.configured && check.executable ? "available" : "failed"}">
        ${check.configured && check.executable ? t("executableReady") : t("executableMissing")}
      </span>
      <small>${check.value || "-"}</small>
    `;
    container.append(row);
  });
}

function renderRuntimeDependencies() {
  const container = $("dependencyStatusList");
  if (!container) return;
  container.innerHTML = "";
  if (!state.runtimeDependencies) {
    $("dependencyStatus").textContent = t("dependencyChecking");
    container.innerHTML = `<div class="status-card"><strong>${t("dependencyChecking")}</strong></div>`;
    return;
  }
  const components = state.runtimeDependencies.components || [];
  const missing = components.filter((item) => item.status !== "available");
  $("dependencyStatus").textContent = missing.length ? `${missing.length} ${statusLabel("not_configured")}` : t("runtimeReady");
  container.innerHTML = components
    .map(
      (item) => `
        <div class="status-card">
          <strong>${state.lang === "zh" ? item.label_zh || item.label || item.id : item.label || item.id}</strong>
          <span class="badge ${item.status}">${statusLabel(item.status)}</span>
          <small>${item.version || item.python || item.url || item.detail?.error || item.id}</small>
        </div>
      `,
    )
    .join("");
}

async function loadRuntimeStatus() {
  state.runtimeStatus = await api("/runtime/status");
  renderRuntimeStatus();
}

async function loadRuntimeDependencies() {
  state.runtimeDependencies = await api("/runtime/dependencies");
  renderRuntimeDependencies();
}

function renderHealthStatus() {
  const key = state.health === "online" ? "apiOnline" : state.health === "offline" ? "offline" : "checking";
  $("healthText").textContent = t(key);
}

async function loadCatalog() {
  state.catalog = await api("/catalog");
  state.health = "online";
  renderHealthStatus();
  if ($("stateDir").value.trim() === ".simops" && state.catalog.default_state_dir) {
    $("stateDir").value = state.catalog.default_state_dir;
  }
  renderCatalog();
}

async function health() {
  try {
    await api("/health");
    state.health = "online";
  } catch (error) {
    state.health = "offline";
  }
  renderHealthStatus();
}

async function generateConfig(mode = "full") {
  const payload = await api("/configs", {
    method: "POST",
    body: JSON.stringify(configPayload(mode)),
  });
  state.configPath = payload.config_path;
  $("configStatus").textContent = payload.config_path;
  toast(t("configGenerated"));
  return payload;
}

async function validateConfig() {
  if (!state.configPath) await generateConfig();
  const payload = await api("/tasks/validate", {
    method: "POST",
    body: JSON.stringify({ config_path: state.configPath, state_dir: $("stateDir").value.trim() || ".simops" }),
  });
  $("configStatus").textContent = `${statusLabel(payload.status)}: ${payload.name}`;
  toast(t("configValid"));
}

async function runPipeline(mode = "full") {
  await generateConfig(mode);
  $("runButton").disabled = true;
  $("collectButton").disabled = true;
  $("runStatus").textContent = statusLabel("running");
  try {
    const payload = await api("/runs", {
      method: "POST",
      body: JSON.stringify({
        config_path: state.configPath,
        state_dir: $("stateDir").value.trim() || ".simops",
        env: envPayload(),
      }),
    });
    $("runStatus").textContent = `${statusLabel(payload.status)}: ${payload.run_id}`;
    toast(mode === "collect" ? t("collectStarted") : `${statusLabel(payload.status)}: ${payload.run_id}`);
    await refresh();
    await loadRunDetails(payload.run_id);
    if (mode === "full") {
      window.location.hash = "#deployment";
    }
  } finally {
    $("runButton").disabled = false;
    $("collectButton").disabled = false;
  }
}

async function refresh() {
  const stateDir = encodeURIComponent($("stateDir").value.trim() || ".simops");
  const [runs, artifacts, datasets, assetLibrary, models, deployments] = await Promise.all([
    api(`/runs?state_dir=${stateDir}&limit=30`),
    api(`/artifacts?state_dir=${stateDir}&limit=200`),
    api(`/datasets?state_dir=${stateDir}&limit=200`),
    api(`/assets/library?state_dir=${stateDir}`),
    api(`/models?state_dir=${stateDir}&limit=200`),
    api(`/deployments?state_dir=${stateDir}&limit=200`),
  ]);
  state.runs = runs;
  state.artifacts = artifacts;
  state.datasets = datasets;
  state.assetLibrary = assetLibrary;
  state.models = models;
  state.deployments = deployments;
  renderRuns(state.runs);
  renderArtifacts(state.artifacts);
  renderDatasets(state.datasets);
  renderAssetLibrary();
  renderModels(state.models);
  renderDeployments(state.deployments);
  await loadRuntimeStatus().catch(() => {});
  await loadRuntimeDependencies().catch(() => {});
  await loadGenerationJobs().catch(() => {});
}

async function loadGenerationJobs() {
  const stateDir = encodeURIComponent($("stateDir").value.trim() || ".simops");
  state.generationJobs = await api(`/generation/jobs?state_dir=${stateDir}&limit=50`);
  renderGenerationJobs(state.generationJobs);
}

function renderGenerationJobs(jobs) {
  const container = $("generationJobList");
  if (!container) return;
  container.innerHTML = "";
  if (!jobs.length) {
    container.innerHTML = `<div class="artifact"><small>${t("noGenerationJobs")}</small></div>`;
    return;
  }
  jobs.forEach((job) => {
    const row = document.createElement("div");
    row.className = "artifact";
    const artifacts = (job.artifacts || [])
      .map((artifact) => `${roleLabel(artifact.role)} ${artifact.sha256}`)
      .join(" / ");
    row.innerHTML = `
      <strong>${job.name}</strong>
      <span class="badge ${job.status || "succeeded"}">${statusLabel(job.status || "succeeded")}</span>
      <small>${job.generator} · ${job.kind} · seed ${job.seed}</small>
      <small>${job.path}</small>
      <small>sha256 ${job.sha256}</small>
      ${artifacts ? `<small>${artifacts}</small>` : ""}
    `;
    container.append(row);
  });
}

function renderRuns(runs) {
  const container = $("runList");
  container.innerHTML = "";
  if (!runs.length) {
    container.innerHTML = `<div class="run"><small>${t("noRuns")}</small></div>`;
    return;
  }
  runs.forEach((run) => {
    const row = document.createElement("button");
    row.className = "run";
    row.type = "button";
    row.innerHTML = `
      <strong>${run.name}</strong>
      <span class="badge ${run.status}">${statusLabel(run.status)}</span>
      <small>${run.id}</small>
    `;
    row.addEventListener("click", () => loadRunDetails(run.id));
    container.append(row);
  });
}

async function loadRunDetails(runId) {
  const stateDir = encodeURIComponent($("stateDir").value.trim() || ".simops");
  const [artifacts, stages] = await Promise.all([
    api(`/runs/${runId}/artifacts?state_dir=${stateDir}`),
    api(`/runs/${runId}/stages?state_dir=${stateDir}`),
  ]);
  state.artifacts = artifacts;
  state.stages = stages;
  renderArtifacts(state.artifacts);
  renderStages(state.stages);
  await refresh();
}

function renderStages(stages) {
  const container = $("stageList");
  if (!container) return;
  container.innerHTML = "";
  if (!stages.length) {
    container.innerHTML = `<div class="stage"><small>${t("noStages")}</small></div>`;
    return;
  }
  stages.forEach((stage) => {
    const row = document.createElement("div");
    row.className = "stage";
    row.innerHTML = `
      <strong>${stage.stage_id}</strong>
      <span class="badge ${stage.status}">${statusLabel(stage.status)}</span>
      <small>${stage.adapter}${stage.returncode === null || stage.returncode === undefined ? "" : ` · exit ${stage.returncode}`}</small>
      ${stage.error ? `<small>${stage.error}</small>` : ""}
    `;
    container.append(row);
  });
}

function renderArtifacts(artifacts) {
  const container = $("artifactList");
  container.innerHTML = "";
  if (!artifacts.length) {
    container.innerHTML = `<div class="artifact"><small>${t("noArtifacts")}</small></div>`;
    return;
  }
  artifacts.slice(0, 80).forEach((artifact) => {
    const row = document.createElement("div");
    row.className = "artifact";
    row.innerHTML = `
      <strong>${artifact.name}</strong>
      <span class="badge available">${roleLabel(artifact.role)}</span>
      <small>${artifact.path}</small>
      <small>sha256 ${artifact.sha256}</small>
    `;
    container.append(row);
  });
}

function renderDatasets(datasets) {
  const container = $("datasetList");
  const paths = new Set(datasets.map((artifact) => artifact.path));
  [...state.selectedDatasets].forEach((path) => {
    if (!paths.has(path)) state.selectedDatasets.delete(path);
  });
  if (state.inspectedDatasetPath && !paths.has(state.inspectedDatasetPath)) state.inspectedDatasetPath = null;
  container.innerHTML = "";
  if (!datasets.length) {
    container.innerHTML = `<div class="artifact"><small>${t("noLerobotDatasets")}</small></div>`;
    $("datasetStatus").textContent = t("noDatasetSelected");
    $("datasetInspectTitle").textContent = t("noDatasetSelected");
    return;
  }
  datasets.forEach((artifact) => {
    const row = document.createElement("div");
    row.className = `artifact dataset-card${state.inspectedDatasetPath === artifact.path ? " selected" : ""}`;
    row.innerHTML = `
      <label class="inline-check"><input type="checkbox" value="${artifact.path}" ${state.selectedDatasets.has(artifact.path) ? "checked" : ""} /> <strong>${artifact.name}</strong></label>
      <span class="badge available">LeRobot</span>
      <small>${artifact.path}</small>
      <small>${artifact.total_episodes ?? "-"} episodes · ${artifact.total_frames ?? "-"} frames · ${artifact.feature_count ?? 0} features · ${artifact.data_files ?? 0} data files</small>
      <small>sha256 ${artifact.sha256 || "-"}</small>
      <button type="button" class="compact-button">${state.lang === "zh" ? "查看" : "Inspect"}</button>
    `;
    row.querySelector("input").addEventListener("change", (event) => {
      if (event.target.checked) state.selectedDatasets.add(artifact.path);
      else state.selectedDatasets.delete(artifact.path);
      $("datasetStatus").textContent = state.selectedDatasets.size
        ? t("datasetSelected", { count: state.selectedDatasets.size })
        : t("noDatasetSelected");
    });
    row.querySelector("button").addEventListener("click", () => inspectDataset(artifact.path).catch((error) => toast(error.message)));
    container.append(row);
  });
  $("datasetStatus").textContent = state.selectedDatasets.size
    ? t("datasetSelected", { count: state.selectedDatasets.size })
    : t("noDatasetSelected");
}

function renderModels(models) {
  renderProductCards("modelList", models || [], (item) => ({
    title: item.name || item.role,
    badge: item.exists === false ? "failed" : "available",
    lines: [
      item.role,
      item.run_id,
      item.path,
      `sha256 ${item.sha256 || "-"}`,
      item.json?.selected_policy ? `selected ${item.json.selected_policy}` : "",
    ],
  }), t("noModels"));
}

function renderDeployments(deployments) {
  renderProductCards("deploymentList", deployments || [], (item) => ({
    title: item.name || item.role,
    badge: item.exists === false ? "failed" : item.status || "available",
    lines: [item.role, item.run_id, item.path, `sha256 ${item.sha256 || "-"}`],
  }), t("noDeployments"));
}

async function inspectDataset(path) {
  const detail = await api(`/datasets/inspect?path=${encodeURIComponent(path)}`);
  state.inspectedDatasetPath = path;
  $("datasetInspectTitle").textContent = path;
  renderDatasets(state.datasets);
  const preview = $("datasetPreview");
  preview.innerHTML = `
    <div class="status-card"><strong>${detail.total_episodes ?? "-"}</strong><small>episodes</small></div>
    <div class="status-card"><strong>${detail.total_frames ?? "-"}</strong><small>frames</small></div>
    <div class="status-card"><strong>${detail.feature_count ?? 0}</strong><small>features</small></div>
    <div class="status-card"><strong>${detail.data_files ?? 0}</strong><small>data files</small></div>
  `;
  $("datasetDetail").textContent = JSON.stringify(
    {
      path: detail.path,
      fps: detail.fps,
      features: detail.features,
      stats_keys: Object.keys(detail.stats || {}),
      files: (detail.files || []).slice(0, 40),
    },
    null,
    2,
  );
}

async function mergeDatasets() {
  const datasetPaths = [...state.selectedDatasets];
  if (datasetPaths.length < 2) {
    toast(t("selectAtLeastTwoDatasets"));
    return;
  }
  const payload = await api("/datasets/merge", {
    method: "POST",
    body: JSON.stringify({ dataset_paths: datasetPaths, output_path: $("mergeOutput").value.trim() }),
  });
  toast(`${t("mergeStatus")} ${statusLabel(payload.status)}`);
}

async function startTeleop() {
  const payload = await api("/simulations/sessions", {
    method: "POST",
    body: JSON.stringify({
      state_dir: $("stateDir").value.trim() || ".simops",
      config_path: state.configPath,
      simulator: $("simulator").value,
      robot: $("robot").value,
      scene: $("scene").value,
      task: $("task").value,
      assets: selectedAssets(),
      sensor_preset: $("sensorPreset").value,
      randomization_seed: Number($("seed").value),
    }),
  });
  state.teleopSessionId = payload.session_id || payload.id;
  renderSimulationApiOutput(payload);
  connectSimulationFrameStream();
  $("teleopStatus").textContent = state.teleopSessionId ? `Session ${state.teleopSessionId}` : t("sessionStarted");
  if (!payload.frame?.preview_scene) {
    await refreshSimulationPreview().catch((error) => toast(error.message));
  }
}

async function sendTeleopAction(action) {
  if (!state.teleopSessionId) {
    toast(t("noTeleopSession"));
    return;
  }
  const payload = await api(`/simulations/sessions/${encodeURIComponent(state.teleopSessionId)}/actions`, {
    method: "POST",
    body: JSON.stringify({ action, velocity: 0.25 }),
  });
  renderSimulationApiOutput(payload);
  $("teleopStatus").textContent = `${t("sentAction")} ${action}`;
}

function connectSimulationFrameStream() {
  if (!state.teleopSessionId) {
    toast(t("noTeleopSession"));
    return;
  }
  const image = $("simRenderFrameImage");
  image.src = `/simulations/sessions/${encodeURIComponent(state.teleopSessionId)}/frames/stream?fps=8&v=${Date.now()}`;
  state.simFrameStreamActive = true;
  state.simFrameStreamSessionId = state.teleopSessionId;
  state.simViewMode = "render";
  $("simViewport").classList.add("has-render-frame");
  $("simFramePanel")?.classList.add("has-frame");
  if ($("simFrameStatus")) $("simFrameStatus").textContent = `${t("frameStreamConnected")} · ${state.teleopSessionId}`;
  applySimulationViewMode();
}

async function closeTeleopSession() {
  if (!state.teleopSessionId) {
    toast(t("noTeleopSession"));
    return;
  }
  const sessionId = state.teleopSessionId;
  const payload = await api(`/simulations/sessions/${encodeURIComponent(sessionId)}`, { method: "DELETE" });
  state.teleopSessionId = null;
  state.simFrameStreamActive = false;
  state.simFrameStreamSessionId = null;
  $("simRenderFrameImage").removeAttribute("src");
  $("simViewport").classList.remove("has-render-frame", "show-render-frame");
  $("simFramePanel")?.classList.remove("has-frame");
  $("teleopStatus").textContent = t("noSession");
  if ($("simFrameStatus")) $("simFrameStatus").textContent = t("renderFrameWaiting");
  renderSimulationApiOutput(payload);
  toast(t("sessionClosed"));
}

async function fetchLatestFrame() {
  if (!state.teleopSessionId) {
    toast(t("noTeleopSession"));
    return;
  }
  const payload = await api(`/simulations/sessions/${encodeURIComponent(state.teleopSessionId)}/frames/latest`);
  renderSimulationApiOutput(payload);
}

async function createPlayback() {
  if (!state.teleopSessionId) {
    toast(t("noTeleopSession"));
    return;
  }
  const payload = await api(`/simulations/sessions/${encodeURIComponent(state.teleopSessionId)}/playback`, {
    method: "POST",
    body: JSON.stringify({
      source_run_id: state.runs[0]?.run_id || null,
      speed: 1.0,
      loop: false,
    }),
  });
  renderSimulationApiOutput(payload);
}

async function loadNativeSimulatorUi() {
  const payload = await api("/simulations/native-ui");
  state.nativeSimulatorUi = payload;
  renderNativeSimulatorUi(payload);
  renderSimulationApiOutput(payload);
}

function renderNativeSimulatorUi(payload) {
  const panel = $("simNativePanel");
  const frame = $("simNativeFrame");
  const status = $("simNativeStatus");
  if (!panel || !frame || !status) return;
  panel.classList.add("visible");
  if (payload?.iframe_url) {
    frame.src = payload.iframe_url;
    frame.hidden = false;
    status.textContent = `${t("nativeUiEmbedded")} · ${payload.status}`;
    return;
  }
  frame.hidden = true;
  frame.removeAttribute("src");
  status.textContent = `${t("nativeUiUnavailable")} · ${payload?.mode || "headless_render_stream"}`;
}

function renderSimulationApiOutput(payload) {
  if (!$("simulationApiOutput")) return;
  $("simulationApiOutput").textContent = JSON.stringify(payload, null, 2);
  const frame = payload?.frame;
  if (frame?.data_base64 && frame?.media_type) {
    if (!(state.simFrameStreamActive && state.simFrameStreamSessionId === state.teleopSessionId)) {
      $("simRenderFrameImage").src = `data:${frame.media_type};base64,${frame.data_base64}`;
    }
    $("simViewport").classList.add("has-render-frame");
    $("simFramePanel")?.classList.add("has-frame");
    if ($("simFrameStatus") && !state.simFrameStreamActive) {
      $("simFrameStatus").textContent = `${t("renderFrameUpdated")} · step ${frame.step ?? "-"}`;
    }
    state.simViewMode = "render";
  }
  if (frame?.preview_scene) {
    ensurePreviewViewer("simThreeViewport", null, "simulationPreviewViewer")
      .then((viewer) => {
        viewer?.setScene(frame.preview_scene);
        $("simViewport").classList.add("has-three");
        if (!frame?.data_base64) {
          $("simFramePanel")?.classList.remove("has-frame");
          if ($("simFrameStatus")) $("simFrameStatus").textContent = t("renderFrameWaiting");
          state.simViewMode = "state";
        }
        applySimulationViewMode();
      })
      .catch((error) => toast(error.message));
  }
  applySimulationViewMode();
}

async function refreshSimulationPreview() {
  const viewer = await ensurePreviewViewer("simThreeViewport", null, "simulationPreviewViewer");
  if (!viewer) return;
  const descriptor = await api("/simulations/preview", {
    method: "POST",
    body: JSON.stringify({
      state_dir: $("stateDir").value.trim() || ".simops",
      config_path: state.configPath,
      simulator: $("simulator").value,
      robot: $("robot").value,
      scene: $("scene").value,
      task: $("task").value,
      assets: selectedAssets(),
      sensor_preset: $("sensorPreset").value,
      randomization_seed: Number($("seed").value),
      render_width: 512,
      render_height: 512,
    }),
  });
  viewer.setScene(descriptor);
  $("simViewport").classList.add("has-three");
  if (!$("simViewport").classList.contains("has-render-frame")) state.simViewMode = "state";
  applySimulationViewMode();
}

function applySimulationViewMode() {
  const viewport = $("simViewport");
  if (!viewport) return;
  const canRender = viewport.classList.contains("has-render-frame");
  const showRender = state.simViewMode === "render" && canRender;
  viewport.classList.toggle("show-render-frame", showRender);
  viewport.classList.toggle("show-state-3d", !showRender);
  $("simRenderViewButton")?.classList.toggle("active", showRender);
  $("simStateViewButton")?.classList.toggle("active", !showRender);
}

async function installBridgeService() {
  $("dependencyStatus").textContent = t("installingRuntime");
  const payload = await api("/runtime/dependencies/install", {
    method: "POST",
    body: JSON.stringify({
      components: ["bridge_service"],
      project_dir: state.runtimeDependencies?.project_dir || "/opt/open-embodied-simops",
    }),
  });
  toast(t("dependencyInstallDone"));
  renderSimulationApiOutput(payload);
  await loadRuntimeDependencies();
  await loadCatalog();
}

function bind() {
  window.addEventListener("hashchange", syncRoute);
  document.querySelectorAll("[data-lang]").forEach((button) => {
    button.addEventListener("click", () => setLanguage(button.dataset.lang));
  });
  $("generateSceneButton").addEventListener("click", () => generateSceneAsset("scene").catch((error) => toast(error.message)));
  $("generateAssetButton").addEventListener("click", () => generateSceneAsset("asset").catch((error) => toast(error.message)));
  $("generatePackageButton").addEventListener("click", () =>
    generateSceneAsset("package").catch((error) => toast(error.message)),
  );
  $("sceneGenerator").addEventListener("change", () => {
    if ($("sceneGenerator").value === "motrixsim_examples") {
      setSelectValue("simulator", "motrixsim");
      applySimulatorDefaults("motrixsim");
    } else if ($("sceneGenerator").value === "maniskill_tabletop") {
      setSelectValue("simulator", "maniskill");
      applySimulatorDefaults("maniskill");
    }
    updateGenerationStatus();
  });
  $("simulator").addEventListener("change", () => {
    applySimulatorDefaults($("simulator").value);
    refreshSimulationPreview().catch((error) => toast(error.message));
  });
  ["robot", "scene", "task"].forEach((id) => {
    $(id).addEventListener("change", () => refreshSimulationPreview().catch((error) => toast(error.message)));
  });
  $("generateConfigButton").addEventListener("click", () => generateConfig().catch((error) => toast(error.message)));
  $("validateButton").addEventListener("click", () => validateConfig().catch((error) => toast(error.message)));
  $("runButton").addEventListener("click", () => runPipeline().catch((error) => toast(error.message)));
  $("trainButton").addEventListener("click", () => runPipeline().catch((error) => toast(error.message)));
  $("refreshButton").addEventListener("click", () => refresh().catch((error) => toast(error.message)));
  $("mergeButton").addEventListener("click", () => mergeDatasets().catch((error) => toast(error.message)));
  $("startTeleopButton").addEventListener("click", () =>
    startTeleop().catch((error) => {
      $("teleopStatus").textContent = error.message;
      toast(error.message);
    }),
  );
  $("latestFrameButton").addEventListener("click", () => fetchLatestFrame().catch((error) => toast(error.message)));
  $("playbackButton").addEventListener("click", () => createPlayback().catch((error) => toast(error.message)));
  $("streamFrameButton").addEventListener("click", () => connectSimulationFrameStream());
  $("nativeUiButton").addEventListener("click", () => loadNativeSimulatorUi().catch((error) => toast(error.message)));
  $("closeTeleopButton").addEventListener("click", () => closeTeleopSession().catch((error) => toast(error.message)));
  $("installBridgeButton").addEventListener("click", () => installBridgeService().catch((error) => toast(error.message)));
  $("collectButton").addEventListener("click", () => runPipeline("collect").catch((error) => toast(error.message)));
  $("simPreviewButton").addEventListener("click", () => refreshSimulationPreview().catch((error) => toast(error.message)));
  $("simRenderViewButton").addEventListener("click", () => {
    state.simViewMode = "render";
    applySimulationViewMode();
  });
  $("simStateViewButton").addEventListener("click", () => {
    state.simViewMode = "state";
    applySimulationViewMode();
  });
  $("simFullscreenToggle").addEventListener("change", (event) => {
    setAppFullscreen($("simViewport"), state.simulationPreviewViewer, event.target.checked);
  });
  $("assetPreviewFullscreenToggle").addEventListener("change", (event) => {
    ensurePreviewViewer("assetPreviewViewport", "assetPreviewStatus", "assetPreviewViewer")
      .then((viewer) => setAppFullscreen($("assetPreviewViewport"), viewer, event.target.checked))
      .catch((error) => toast(error.message));
  });
  document.querySelectorAll(".teleop-pad button").forEach((button) => {
    button.addEventListener("click", () => sendTeleopAction(button.dataset.action).catch((error) => toast(error.message)));
  });
  $("simViewport").addEventListener("keydown", (event) => {
    const map = {
      ArrowUp: "forward",
      ArrowDown: "backward",
      ArrowLeft: "left",
      ArrowRight: "right",
      e: "lift",
      E: "lift",
      q: "lower",
      Q: "lower",
      " ": "stop",
    };
    if (map[event.key]) {
      event.preventDefault();
      sendTeleopAction(map[event.key]).catch((error) => toast(error.message));
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") exitAppFullscreen();
  });
}

async function init() {
  applyTranslations();
  bind();
  await health();
  await loadCatalog();
  await loadRuntimeStatus().catch(() => {});
  await loadRuntimeDependencies().catch(() => {});
  await refresh().catch(() => {});
  await refreshSimulationPreview().catch(() => {});
}

init().catch((error) => toast(error.message));

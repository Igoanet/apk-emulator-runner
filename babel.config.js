module.exports = function (api) {
  // NODE_ENV pe cache — release bundle me console.* strip hota hai (logcat se
  // info leakage band, owner hardening requirement 2026-08-17); dev me sab rehta hai.
  api.cache.using(() => process.env.NODE_ENV ?? "development");
  const plugins = [];
  if (api.env("production")) plugins.push("transform-remove-console");
  return {
    presets: [["babel-preset-expo", { unstable_transformImportMeta: true }]],
    plugins,
  };
};

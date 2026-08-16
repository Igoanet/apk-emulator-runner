const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);

// Watchers bachao — inotify limit 65536 per-user hai (root nahi, badha nahi sakte)
// aur pnpm monorepo ka node_modules crawl akela hi limit kha jata hai (ENOSPC crash).
//
// blockList: map se hi nikaal do (resolve bhi nahi honge)
//  - .build/ = local APK toolchain (~5GB JDK/SDK/gradle caches)
//  - */android/ = native project dirs — metro ko sirf JS chahiye
// NOTE: multi-pattern merge pe metro "different flags" error deta hai — EK combined RegExp.
config.resolver.blockList =
  /([\\/]\.build[\\/]|[\\/]android[\\/]|\.expo[\\/]types|\/__tests__\/.*$)/;

// watchPathIgnorePatterns: map me rehte hain (resolution kaam karti hai)
// par inotify watcher NAHI lagta — deps kabhi badalte nahi, isliye safe.
// Yehi asli watcher savings hai (~50k+ dirs).
config.watchPathIgnorePatterns = [
  /[\\/]node_modules[\\/]/,
  /[\\/]\.build[\\/]/,
  /[\\/]android[\\/]/,
];

module.exports = config;

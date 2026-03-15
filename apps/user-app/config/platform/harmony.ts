const harmonyConfig = {
  harmony: {
    compiler: 'vite',
    projectPath: process.env.HARMONY_PROJECT_PATH ?? '',
    hapName: process.env.HARMONY_HAP_NAME ?? 'entry',
  },
  output: {
    filename: 'js/[name].js',
    chunkFilename: 'js/[name].js',
  },
};

export default harmonyConfig;

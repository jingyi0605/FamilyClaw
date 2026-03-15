const h5Config = {
  router: {
    mode: 'browser',
  },
  output: {
    filename: 'js/[name].[hash:8].js',
    chunkFilename: 'js/[name].[chunkhash:8].js',
  },
};

export default h5Config;

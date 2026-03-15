{
  target: [
    'web',
    'es5'
  ],
  watchOptions: {
    aggregateTimeout: 200
  },
  mode: 'production',
  devtool: false,
  output: {
    chunkLoadingGlobal: 'webpackJsonp',
    path: 'C:\\Code\\FamilyClaw\\apps\\user-app\\dist',
    filename: 'js/[name].[hash:8].js',
    chunkFilename: 'js/[name].[chunkhash:8].js',
    publicPath: '/'
  },
  resolve: {
    symlinks: true,
    alias: {
      '@tarojs/runtime': 'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\@tarojs\\runtime\\dist\\index.js',
      '@tarojs/shared': 'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\@tarojs\\shared\\dist\\index.js',
      '@': 'C:\\Code\\FamilyClaw\\apps\\user-app\\src',
      react$: 'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\react\\index.js',
      'react-dom$': 'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\react-dom\\index.js',
      '@tarojs/components$': 'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\@tarojs\\components\\lib\\react\\index.js',
      '@tarojs/components/lib': 'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\@tarojs\\components\\lib',
      '@tarojs/router$': 'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\@tarojs\\router\\dist\\index.js',
      '@tarojs/taro': 'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\@tarojs\\plugin-platform-h5\\dist\\runtime\\apis\\index.js'
    },
    extensions: [
      '.js',
      '.jsx',
      '.ts',
      '.tsx',
      '.mjs',
      '.vue'
    ],
    mainFields: [
      'browser',
      'module',
      'jsnext:main',
      'main'
    ],
    plugins: [
      /* config.resolve.plugin('MultiPlatformPlugin') */
      new MultiPlatformPlugin(
        'described-resolve',
        'resolve',
        {
          chain: {
            parent: undefined,
            store: new Map([
              [
                'target',
                [
                  'web',
                  'es5'
                ]
              ],
              [
                'watchOptions',
                {
                  aggregateTimeout: 200
                }
              ],
              [
                'mode',
                'production'
              ],
              [
                'devtool',
                false
              ],
              [
                'externals',
                {}
              ]
            ]),
            devServer: {
              store: new Map([]),
              allowedHosts: {
                store: new Set([])
              },
              shorthands: [
                'after',
                'before',
                'bonjour',
                'clientLogLevel',
                'color',
                'compress',
                'contentBase',
                'disableHostCheck',
                'filename',
                'headers',
                'historyApiFallback',
                'host',
                'hot',
                'hotOnly',
                'http2',
                'https',
                'index',
                'info',
                'inline',
                'lazy',
                'mimeTypes',
                'noInfo',
                'open',
                'openPage',
                'overlay',
                'pfx',
                'pfxPassphrase',
                'port',
                'proxy',
                'progress',
                'public',
                'publicPath',
                'quiet',
                'setup',
                'socket',
                'sockHost',
                'sockPath',
                'sockPort',
                'staticOptions',
                'stats',
                'stdin',
                'useLocalIp',
                'watchContentBase',
                'watchOptions',
                'writeToDisk'
              ],
              after: (value) => this.set(method, value),
              before: (value) => this.set(method, value),
              bonjour: (value) => this.set(method, value),
              clientLogLevel: (value) => this.set(method, value),
              color: (value) => this.set(method, value),
              compress: (value) => this.set(method, value),
              contentBase: (value) => this.set(method, value),
              disableHostCheck: (value) => this.set(method, value),
              filename: (value) => this.set(method, value),
              headers: (value) => this.set(method, value),
              historyApiFallback: (value) => this.set(method, value),
              host: (value) => this.set(method, value),
              hot: (value) => this.set(method, value),
              hotOnly: (value) => this.set(method, value),
              http2: (value) => this.set(method, value),
              https: (value) => this.set(method, value),
              index: (value) => this.set(method, value),
              info: (value) => this.set(method, value),
              inline: (value) => this.set(method, value),
              lazy: (value) => this.set(method, value),
              mimeTypes: (value) => this.set(method, value),
              noInfo: (value) => this.set(method, value),
              open: (value) => this.set(method, value),
              openPage: (value) => this.set(method, value),
              overlay: (value) => this.set(method, value),
              pfx: (value) => this.set(method, value),
              pfxPassphrase: (value) => this.set(method, value),
              port: (value) => this.set(method, value),
              proxy: (value) => this.set(method, value),
              progress: (value) => this.set(method, value),
              'public': (value) => this.set(method, value),
              publicPath: (value) => this.set(method, value),
              quiet: (value) => this.set(method, value),
              setup: (value) => this.set(method, value),
              socket: (value) => this.set(method, value),
              sockHost: (value) => this.set(method, value),
              sockPath: (value) => this.set(method, value),
              sockPort: (value) => this.set(method, value),
              staticOptions: (value) => this.set(method, value),
              stats: (value) => this.set(method, value),
              stdin: (value) => this.set(method, value),
              useLocalIp: (value) => this.set(method, value),
              watchContentBase: (value) => this.set(method, value),
              watchOptions: (value) => this.set(method, value),
              writeToDisk: (value) => this.set(method, value)
            },
            entryPoints: {
              store: new Map([
                [
                  'app',
                  {
                    store: new Set([
                      'C:\\Code\\FamilyClaw\\apps\\user-app\\src\\app.config'
                    ])
                  }
                ]
              ])
            },
            module: {
              store: new Map([]),
              rules: {
                store: new Map([
                  [
                    'taroStyle',
                    {
                      store: new Map([
                        [
                          'test',
                          /\.(css|scss|sass|less|styl|stylus|wxss|acss|ttss|jxss|qss)(\?.*)?$/
                        ]
                      ]),
                      name: 'taroStyle',
                      names: [
                        'taroStyle'
                      ],
                      ruleType: 'rule',
                      ruleTypes: [
                        'rule'
                      ],
                      uses: {
                        store: new Map([
                          [
                            '0',
                            {
                              store: new Map([
                                [
                                  'loader',
                                  'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\style-loader\\dist\\cjs.js'
                                ],
                                [
                                  'options',
                                  {
                                    insert: function () { /* omitted long function */ }
                                  }
                                ]
                              ]),
                              name: '0',
                              shorthands: [
                                'loader',
                                'options'
                              ],
                              loader: (value) => this.set(method, value),
                              options: (value) => this.set(method, value)
                            }
                          ]
                        ])
                      },
                      include: {
                        store: new Set([
                          (filename) => isTaroModule(filename)
                        ])
                      },
                      exclude: {
                        store: new Set([])
                      },
                      rules: {
                        store: new Map([])
                      },
                      oneOfs: {
                        store: new Map([])
                      },
                      resolve: {
                        store: new Map([]),
                        alias: {
                          store: new Map([])
                        },
                        aliasFields: {
                          store: new Set([])
                        },
                        descriptionFiles: {
                          store: new Set([])
                        },
                        extensions: {
                          store: new Set([])
                        },
                        mainFields: {
                          store: new Set([])
                        },
                        mainFiles: {
                          store: new Set([])
                        },
                        modules: {
                          store: new Set([])
                        },
                        plugins: {
                          store: new Map([])
                        },
                        shorthands: [
                          'cachePredicate',
                          'cacheWithContext',
                          'concord',
                          'enforceExtension',
                          'enforceModuleExtension',
                          'symlinks',
                          'unsafeCache'
                        ],
                        cachePredicate: (value) => this.set(method, value),
                        cacheWithContext: (value) => this.set(method, value),
                        concord: (value) => this.set(method, value),
                        enforceExtension: (value) => this.set(method, value),
                        enforceModuleExtension: (value) => this.set(method, value),
                        symlinks: (value) => this.set(method, value),
                        unsafeCache: (value) => this.set(method, value)
                      },
                      shorthands: [
                        'enforce',
                        'issuer',
                        'parser',
                        'resource',
                        'resourceQuery',
                        'sideEffects',
                        'test',
                        'type'
                      ],
                      enforce: (value) => this.set(method, value),
                      issuer: (value) => this.set(method, value),
                      parser: (value) => this.set(method, value),
                      resource: (value) => this.set(method, value),
                      resourceQuery: (value) => this.set(method, value),
                      sideEffects: (value) => this.set(method, value),
                      test: (value) => this.set(method, value),
                      type: (value) => this.set(method, value)
                    }
                  ],
                  [
                    'customStyle',
                    {
                      store: new Map([
                        [
                          'test',
                          /\.(css|scss|sass|less|styl|stylus|wxss|acss|ttss|jxss|qss)(\?.*)?$/
                        ]
                      ]),
                      name: 'customStyle',
                      names: [
                        'customStyle'
                      ],
                      ruleType: 'rule',
                      ruleTypes: [
                        'rule'
                      ],
                      uses: {
                        store: new Map([
                          [
                            '0',
                            {
                              store: new Map([
                                [
                                  'loader',
                                  'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\mini-css-extract-plugin\\dist\\loader.js'
                                ]
                              ]),
                              name: '0',
                              shorthands: [
                                'loader',
                                'options'
                              ],
                              loader: (value) => this.set(method, value),
                              options: (value) => this.set(method, value)
                            }
                          ]
                        ])
                      },
                      include: {
                        store: new Set([])
                      },
                      exclude: {
                        store: new Set([
                          (filename) => isTaroModule(filename)
                        ])
                      },
                      rules: {
                        store: new Map([])
                      },
                      oneOfs: {
                        store: new Map([])
                      },
                      resolve: {
                        store: new Map([]),
                        alias: {
                          store: new Map([])
                        },
                        aliasFields: {
                          store: new Set([])
                        },
                        descriptionFiles: {
                          store: new Set([])
                        },
                        extensions: {
                          store: new Set([])
                        },
                        mainFields: {
                          store: new Set([])
                        },
                        mainFiles: {
                          store: new Set([])
                        },
                        modules: {
                          store: new Set([])
                        },
                        plugins: {
                          store: new Map([])
                        },
                        shorthands: [
                          'cachePredicate',
                          'cacheWithContext',
                          'concord',
                          'enforceExtension',
                          'enforceModuleExtension',
                          'symlinks',
                          'unsafeCache'
                        ],
                        cachePredicate: (value) => this.set(method, value),
                        cacheWithContext: (value) => this.set(method, value),
                        concord: (value) => this.set(method, value),
                        enforceExtension: (value) => this.set(method, value),
                        enforceModuleExtension: (value) => this.set(method, value),
                        symlinks: (value) => this.set(method, value),
                        unsafeCache: (value) => this.set(method, value)
                      },
                      shorthands: [
                        'enforce',
                        'issuer',
                        'parser',
                        'resource',
                        'resourceQuery',
                        'sideEffects',
                        'test',
                        'type'
                      ],
                      enforce: (value) => this.set(method, value),
                      issuer: (value) => this.set(method, value),
                      parser: (value) => this.set(method, value),
                      resource: (value) => this.set(method, value),
                      resourceQuery: (value) => this.set(method, value),
                      sideEffects: (value) => this.set(method, value),
                      test: (value) => this.set(method, value),
                      type: (value) => this.set(method, value)
                    }
                  ],
                  [
                    'css',
                    {
                      store: new Map([
                        [
                          'test',
                          /\.(css|scss|sass|less|styl|stylus|wxss|acss|ttss|jxss|qss)(\?.*)?$/
                        ]
                      ]),
                      name: 'css',
                      names: [
                        'css'
                      ],
                      ruleType: 'rule',
                      ruleTypes: [
                        'rule'
                      ],
                      uses: {
                        store: new Map([])
                      },
                      include: {
                        store: new Set([])
                      },
                      exclude: {
                        store: new Set([])
                      },
                      rules: {
                        store: new Map([])
                      },
                      oneOfs: {
                        store: new Map([
                          [
                            '0',
                            {
                              store: new Map([]),
                              name: '0',
                              names: [
                                'css',
                                '0'
                              ],
                              ruleType: 'oneOf',
                              ruleTypes: [
                                'rule',
                                'oneOf'
                              ],
                              uses: {
                                store: new Map([
                                  [
                                    '0',
                                    {
                                      store: new Map([
                                        [
                                          'loader',
                                          'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\css-loader\\dist\\cjs.js'
                                        ],
                                        [
                                          'options',
                                          {
                                            importLoaders: 1,
                                            modules: false
                                          }
                                        ]
                                      ]),
                                      name: '0',
                                      shorthands: [
                                        'loader',
                                        'options'
                                      ],
                                      loader: (value) => this.set(method, value),
                                      options: (value) => this.set(method, value)
                                    }
                                  ]
                                ])
                              },
                              include: {
                                store: new Set([])
                              },
                              exclude: {
                                store: new Set([])
                              },
                              rules: {
                                store: new Map([])
                              },
                              oneOfs: {
                                store: new Map([])
                              },
                              resolve: {
                                store: new Map([]),
                                alias: {
                                  store: new Map([])
                                },
                                aliasFields: {
                                  store: new Set([])
                                },
                                descriptionFiles: {
                                  store: new Set([])
                                },
                                extensions: {
                                  store: new Set([])
                                },
                                mainFields: {
                                  store: new Set([])
                                },
                                mainFiles: {
                                  store: new Set([])
                                },
                                modules: {
                                  store: new Set([])
                                },
                                plugins: {
                                  store: new Map([])
                                },
                                shorthands: [
                                  'cachePredicate',
                                  'cacheWithContext',
                                  'concord',
                                  'enforceExtension',
                                  'enforceModuleExtension',
                                  'symlinks',
                                  'unsafeCache'
                                ],
                                cachePredicate: (value) => this.set(method, value),
                                cacheWithContext: (value) => this.set(method, value),
                                concord: (value) => this.set(method, value),
                                enforceExtension: (value) => this.set(method, value),
                                enforceModuleExtension: (value) => this.set(method, value),
                                symlinks: (value) => this.set(method, value),
                                unsafeCache: (value) => this.set(method, value)
                              },
                              shorthands: [
                                'enforce',
                                'issuer',
                                'parser',
                                'resource',
                                'resourceQuery',
                                'sideEffects',
                                'test',
                                'type'
                              ],
                              enforce: (value) => this.set(method, value),
                              issuer: (value) => this.set(method, value),
                              parser: (value) => this.set(method, value),
                              resource: (value) => this.set(method, value),
                              resourceQuery: (value) => this.set(method, value),
                              sideEffects: (value) => this.set(method, value),
                              test: (value) => this.set(method, value),
                              type: (value) => this.set(method, value)
                            }
                          ]
                        ])
                      },
                      resolve: {
                        store: new Map([]),
                        alias: {
                          store: new Map([])
                        },
                        aliasFields: {
                          store: new Set([])
                        },
                        descriptionFiles: {
                          store: new Set([])
                        },
                        extensions: {
                          store: new Set([])
                        },
                        mainFields: {
                          store: new Set([])
                        },
                        mainFiles: {
                          store: new Set([])
                        },
                        modules: {
                          store: new Set([])
                        },
                        plugins: {
                          store: new Map([])
                        },
                        shorthands: [
                          'cachePredicate',
                          'cacheWithContext',
                          'concord',
                          'enforceExtension',
                          'enforceModuleExtension',
                          'symlinks',
                          'unsafeCache'
                        ],
                        cachePredicate: (value) => this.set(method, value),
                        cacheWithContext: (value) => this.set(method, value),
                        concord: (value) => this.set(method, value),
                        enforceExtension: (value) => this.set(method, value),
                        enforceModuleExtension: (value) => this.set(method, value),
                        symlinks: (value) => this.set(method, value),
                        unsafeCache: (value) => this.set(method, value)
                      },
                      shorthands: [
                        'enforce',
                        'issuer',
                        'parser',
                        'resource',
                        'resourceQuery',
                        'sideEffects',
                        'test',
                        'type'
                      ],
                      enforce: (value) => this.set(method, value),
                      issuer: (value) => this.set(method, value),
                      parser: (value) => this.set(method, value),
                      resource: (value) => this.set(method, value),
                      resourceQuery: (value) => this.set(method, value),
                      sideEffects: (value) => this.set(method, value),
                      test: (value) => this.set(method, value),
                      type: (value) => this.set(method, value)
                    }
                  ],
                  [
                    'postcss',
                    {
                      store: new Map([
                        [
                          'test',
                          /\.(css|scss|sass|less|styl|stylus|wxss|acss|ttss|jxss|qss)(\?.*)?$/
                        ]
                      ]),
                      name: 'postcss',
                      names: [
                        'postcss'
                      ],
                      ruleType: 'rule',
                      ruleTypes: [
                        'rule'
                      ],
                      uses: {
                        store: new Map([
                          [
                            '0',
                            {
                              store: new Map([
                                [
                                  'loader',
                                  'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\postcss-loader\\dist\\cjs.js'
                                ],
                                [
                                  'options',
                                  {
                                    postcssOptions: {
                                      plugins: [
                                        {
                                          postcssPlugin: 'postcss-import',
                                          Once: function () { /* omitted long function */ }
                                        },
                                        {
                                          browsers: undefined,
                                          info: function () { /* omitted long function */ },
                                          options: {
                                            flexbox: 'no-2009'
                                          },
                                          postcssPlugin: 'autoprefixer',
                                          prepare: function () { /* omitted long function */ }
                                        },
                                        {
                                          postcssPlugin: 'postcss-pxtransform',
                                          prepare: function () { /* omitted long function */ }
                                        },
                                        {
                                          postcssPlugin: 'postcss-html-transform',
                                          Rule: function () { /* omitted long function */ },
                                          Declaration: function () { /* omitted long function */ }
                                        },
                                        {
                                          postcssPlugin: 'postcss-plugin-constparse',
                                          Declaration: function () { /* omitted long function */ }
                                        },
                                        {
                                          postcssPlugin: 'postcss-alias',
                                          Once: function () { /* omitted long function */ }
                                        },
                                        {
                                          postcssPlugin: 'postcss-url',
                                          Once: function () { /* omitted long function */ }
                                        }
                                      ]
                                    }
                                  }
                                ]
                              ]),
                              name: '0',
                              shorthands: [
                                'loader',
                                'options'
                              ],
                              loader: (value) => this.set(method, value),
                              options: (value) => this.set(method, value)
                            }
                          ]
                        ])
                      },
                      include: {
                        store: new Set([])
                      },
                      exclude: {
                        store: new Set([
                          function () { /* omitted long function */ }
                        ])
                      },
                      rules: {
                        store: new Map([])
                      },
                      oneOfs: {
                        store: new Map([])
                      },
                      resolve: {
                        store: new Map([]),
                        alias: {
                          store: new Map([])
                        },
                        aliasFields: {
                          store: new Set([])
                        },
                        descriptionFiles: {
                          store: new Set([])
                        },
                        extensions: {
                          store: new Set([])
                        },
                        mainFields: {
                          store: new Set([])
                        },
                        mainFiles: {
                          store: new Set([])
                        },
                        modules: {
                          store: new Set([])
                        },
                        plugins: {
                          store: new Map([])
                        },
                        shorthands: [
                          'cachePredicate',
                          'cacheWithContext',
                          'concord',
                          'enforceExtension',
                          'enforceModuleExtension',
                          'symlinks',
                          'unsafeCache'
                        ],
                        cachePredicate: (value) => this.set(method, value),
                        cacheWithContext: (value) => this.set(method, value),
                        concord: (value) => this.set(method, value),
                        enforceExtension: (value) => this.set(method, value),
                        enforceModuleExtension: (value) => this.set(method, value),
                        symlinks: (value) => this.set(method, value),
                        unsafeCache: (value) => this.set(method, value)
                      },
                      shorthands: [
                        'enforce',
                        'issuer',
                        'parser',
                        'resource',
                        'resourceQuery',
                        'sideEffects',
                        'test',
                        'type'
                      ],
                      enforce: (value) => this.set(method, value),
                      issuer: (value) => this.set(method, value),
                      parser: (value) => this.set(method, value),
                      resource: (value) => this.set(method, value),
                      resourceQuery: (value) => this.set(method, value),
                      sideEffects: (value) => this.set(method, value),
                      test: (value) => this.set(method, value),
                      type: (value) => this.set(method, value)
                    }
                  ],
                  [
                    'sass',
                    {
                      store: new Map([
                        [
                          'test',
                          /\.sass$/
                        ]
                      ]),
                      name: 'sass',
                      names: [
                        'sass'
                      ],
                      ruleType: 'rule',
                      ruleTypes: [
                        'rule'
                      ],
                      uses: {
                        store: new Map([
                          [
                            '0',
                            {
                              store: new Map([
                                [
                                  'loader',
                                  'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\resolve-url-loader\\index.js'
                                ],
                                [
                                  'options',
                                  {}
                                ]
                              ]),
                              name: '0',
                              shorthands: [
                                'loader',
                                'options'
                              ],
                              loader: (value) => this.set(method, value),
                              options: (value) => this.set(method, value)
                            }
                          ],
                          [
                            '1',
                            {
                              store: new Map([
                                [
                                  'loader',
                                  'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\sass-loader\\dist\\cjs.js'
                                ],
                                [
                                  'options',
                                  {
                                    sourceMap: true,
                                    implementation: {
                                      load: function () { /* omitted long function */ },
                                      compile: function () {
                                        return _call(f, Array.prototype.slice.apply(arguments));
                                      },
                                      compileString: function () {
                                        return _call(f, Array.prototype.slice.apply(arguments));
                                      },
                                      compileAsync: function () {
                                        return _call(f, Array.prototype.slice.apply(arguments));
                                      },
                                      compileStringAsync: function () {
                                        return _call(f, Array.prototype.slice.apply(arguments));
                                      },
                                      initCompiler: function () {
                                        return _call(f, Array.prototype.slice.apply(arguments));
                                      },
                                      initAsyncCompiler: function () {
                                        return _call(f, Array.prototype.slice.apply(arguments));
                                      },
                                      Compiler: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      AsyncCompiler: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      Value: function Value0() {
                                      },
                                      SassBoolean: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      SassArgumentList: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      SassCalculation: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      CalculationOperation: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      CalculationInterpolation: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      SassColor: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      SassFunction: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      SassMixin: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      SassList: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      SassMap: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      SassNumber: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      SassString: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      sassNull: {},
                                      sassTrue: {
                                        value: true
                                      },
                                      sassFalse: {
                                        value: false
                                      },
                                      Exception: function () { /* omitted long function */ },
                                      Logger: {
                                        silent: {
                                          warn: function () {
                                            return _call(f, Array.prototype.slice.apply(arguments));
                                          },
                                          debug: function () {
                                            return _call(f, Array.prototype.slice.apply(arguments));
                                          }
                                        }
                                      },
                                      NodePackageImporter: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      deprecations: {
                                        'call-string': {
                                          id: 'call-string',
                                          status: 'active',
                                          description: 'Passing a string directly to meta.call().',
                                          deprecatedIn: {
                                            major: 0,
                                            minor: 0,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '0.0.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        elseif: {
                                          id: 'elseif',
                                          status: 'active',
                                          description: '@elseif.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 3,
                                            patch: 2,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.3.2'
                                          },
                                          obsoleteIn: null
                                        },
                                        'moz-document': {
                                          id: 'moz-document',
                                          status: 'active',
                                          description: '@-moz-document.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 7,
                                            patch: 2,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.7.2'
                                          },
                                          obsoleteIn: null
                                        },
                                        'relative-canonical': {
                                          id: 'relative-canonical',
                                          status: 'active',
                                          description: 'Imports using relative canonical URLs.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 14,
                                            patch: 2,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.14.2'
                                          },
                                          obsoleteIn: null
                                        },
                                        'new-global': {
                                          id: 'new-global',
                                          status: 'active',
                                          description: 'Declaring new variables with !global.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 17,
                                            patch: 2,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.17.2'
                                          },
                                          obsoleteIn: null
                                        },
                                        'color-module-compat': {
                                          id: 'color-module-compat',
                                          status: 'active',
                                          description: 'Using color module functions in place of plain CSS functions.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 23,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.23.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'slash-div': {
                                          id: 'slash-div',
                                          status: 'active',
                                          description: '/ operator for division.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 33,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.33.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'bogus-combinators': {
                                          id: 'bogus-combinators',
                                          status: 'active',
                                          description: 'Leading, trailing, and repeated combinators.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 54,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.54.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'strict-unary': {
                                          id: 'strict-unary',
                                          status: 'active',
                                          description: 'Ambiguous + and - operators.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 55,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.55.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'function-units': {
                                          id: 'function-units',
                                          status: 'active',
                                          description: 'Passing invalid units to built-in functions.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 56,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.56.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'duplicate-var-flags': {
                                          id: 'duplicate-var-flags',
                                          status: 'active',
                                          description: 'Using !default or !global multiple times for one variable.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 62,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.62.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'null-alpha': {
                                          id: 'null-alpha',
                                          status: 'active',
                                          description: 'Passing null as alpha in the JS API.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 62,
                                            patch: 3,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.62.3'
                                          },
                                          obsoleteIn: null
                                        },
                                        'abs-percent': {
                                          id: 'abs-percent',
                                          status: 'active',
                                          description: 'Passing percentages to the Sass abs() function.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 65,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.65.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'fs-importer-cwd': {
                                          id: 'fs-importer-cwd',
                                          status: 'active',
                                          description: 'Using the current working directory as an implicit load path.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 73,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.73.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'css-function-mixin': {
                                          id: 'css-function-mixin',
                                          status: 'obsolete',
                                          description: 'Function and mixin names beginning with --.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 76,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.76.0'
                                          },
                                          obsoleteIn: {
                                            major: 1,
                                            minor: 94,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.94.0'
                                          }
                                        },
                                        'mixed-decls': {
                                          id: 'mixed-decls',
                                          status: 'obsolete',
                                          description: 'Declarations after or between nested rules.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 77,
                                            patch: 7,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.77.7'
                                          },
                                          obsoleteIn: {
                                            major: 1,
                                            minor: 92,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.92.0'
                                          }
                                        },
                                        'feature-exists': {
                                          id: 'feature-exists',
                                          status: 'active',
                                          description: 'meta.feature-exists',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 78,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.78.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'color-4-api': {
                                          id: 'color-4-api',
                                          status: 'active',
                                          description: 'Certain uses of built-in sass:color functions.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 79,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.79.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'color-functions': {
                                          id: 'color-functions',
                                          status: 'active',
                                          description: 'Using global color functions instead of sass:color.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 79,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.79.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'legacy-js-api': {
                                          id: 'legacy-js-api',
                                          status: 'active',
                                          description: 'Legacy JS API.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 79,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.79.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'import': {
                                          id: 'import',
                                          status: 'active',
                                          description: '@import rules.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 80,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.80.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'global-builtin': {
                                          id: 'global-builtin',
                                          status: 'active',
                                          description: 'Global built-in functions that are available in sass: modules.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 80,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.80.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'type-function': {
                                          id: 'type-function',
                                          status: 'obsolete',
                                          description: 'Functions named "type".',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 86,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.86.0'
                                          },
                                          obsoleteIn: {
                                            major: 1,
                                            minor: 92,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.92.0'
                                          }
                                        },
                                        'compile-string-relative-url': {
                                          id: 'compile-string-relative-url',
                                          status: 'active',
                                          description: 'Passing a relative url to compileString().',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 88,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.88.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'misplaced-rest': {
                                          id: 'misplaced-rest',
                                          status: 'active',
                                          description: 'A rest parameter before a positional or named parameter.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 91,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.91.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'with-private': {
                                          id: 'with-private',
                                          status: 'active',
                                          description: 'Configuring private variables in @use, @forward, or load-css().',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 92,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.92.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'if-function': {
                                          id: 'if-function',
                                          status: 'active',
                                          description: 'The Sass if($condition, $if-true, $if-false) function.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 95,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.95.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'user-authored': {
                                          id: 'user-authored',
                                          status: 'user',
                                          description: null,
                                          deprecatedIn: null,
                                          obsoleteIn: null
                                        }
                                      },
                                      Version: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      loadParserExports_: function () {
                                        return _call(f, Array.prototype.slice.apply(arguments));
                                      },
                                      info: 'dart-sass\t1.98.0\t(Sass Compiler)\t[Dart]\ndart2js\t3.11.2\t(Dart Compiler)\t[Dart]',
                                      render: function () {
                                        return _call(f, Array.prototype.slice.apply(arguments));
                                      },
                                      renderSync: function () {
                                        return _call(f, Array.prototype.slice.apply(arguments));
                                      },
                                      types: {
                                        Boolean: function () {
                                          return _call(f, this, Array.prototype.slice.apply(arguments));
                                        },
                                        Color: function () {
                                          return _call(f, this, Array.prototype.slice.apply(arguments));
                                        },
                                        List: function () {
                                          return _call(f, this, Array.prototype.slice.apply(arguments));
                                        },
                                        Map: function () {
                                          return _call(f, this, Array.prototype.slice.apply(arguments));
                                        },
                                        Null: function () {
                                          return _call(f, this, Array.prototype.slice.apply(arguments));
                                        },
                                        Number: function () {
                                          return _call(f, this, Array.prototype.slice.apply(arguments));
                                        },
                                        String: function () {
                                          return _call(f, this, Array.prototype.slice.apply(arguments));
                                        },
                                        Error: function Error() { [native code] }
                                      },
                                      NULL: {},
                                      TRUE: {
                                        value: true
                                      },
                                      FALSE: {
                                        value: false
                                      },
                                      cli_pkg_main_0_: function () {
                                        return _call(f, Array.prototype.slice.apply(arguments));
                                      }
                                    },
                                    sassOptions: {
                                      outputStyle: 'expanded',
                                      silenceDeprecations: [
                                        'legacy-js-api'
                                      ],
                                      importer: function () { /* omitted long function */ },
                                      indentedSyntax: true
                                    }
                                  }
                                ]
                              ]),
                              name: '1',
                              shorthands: [
                                'loader',
                                'options'
                              ],
                              loader: (value) => this.set(method, value),
                              options: (value) => this.set(method, value)
                            }
                          ]
                        ])
                      },
                      include: {
                        store: new Set([])
                      },
                      exclude: {
                        store: new Set([])
                      },
                      rules: {
                        store: new Map([])
                      },
                      oneOfs: {
                        store: new Map([])
                      },
                      resolve: {
                        store: new Map([]),
                        alias: {
                          store: new Map([])
                        },
                        aliasFields: {
                          store: new Set([])
                        },
                        descriptionFiles: {
                          store: new Set([])
                        },
                        extensions: {
                          store: new Set([])
                        },
                        mainFields: {
                          store: new Set([])
                        },
                        mainFiles: {
                          store: new Set([])
                        },
                        modules: {
                          store: new Set([])
                        },
                        plugins: {
                          store: new Map([])
                        },
                        shorthands: [
                          'cachePredicate',
                          'cacheWithContext',
                          'concord',
                          'enforceExtension',
                          'enforceModuleExtension',
                          'symlinks',
                          'unsafeCache'
                        ],
                        cachePredicate: (value) => this.set(method, value),
                        cacheWithContext: (value) => this.set(method, value),
                        concord: (value) => this.set(method, value),
                        enforceExtension: (value) => this.set(method, value),
                        enforceModuleExtension: (value) => this.set(method, value),
                        symlinks: (value) => this.set(method, value),
                        unsafeCache: (value) => this.set(method, value)
                      },
                      shorthands: [
                        'enforce',
                        'issuer',
                        'parser',
                        'resource',
                        'resourceQuery',
                        'sideEffects',
                        'test',
                        'type'
                      ],
                      enforce: (value) => this.set(method, value),
                      issuer: (value) => this.set(method, value),
                      parser: (value) => this.set(method, value),
                      resource: (value) => this.set(method, value),
                      resourceQuery: (value) => this.set(method, value),
                      sideEffects: (value) => this.set(method, value),
                      test: (value) => this.set(method, value),
                      type: (value) => this.set(method, value)
                    }
                  ],
                  [
                    'scss',
                    {
                      store: new Map([
                        [
                          'test',
                          /\.scss$/
                        ]
                      ]),
                      name: 'scss',
                      names: [
                        'scss'
                      ],
                      ruleType: 'rule',
                      ruleTypes: [
                        'rule'
                      ],
                      uses: {
                        store: new Map([
                          [
                            '0',
                            {
                              store: new Map([
                                [
                                  'loader',
                                  'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\resolve-url-loader\\index.js'
                                ],
                                [
                                  'options',
                                  {}
                                ]
                              ]),
                              name: '0',
                              shorthands: [
                                'loader',
                                'options'
                              ],
                              loader: (value) => this.set(method, value),
                              options: (value) => this.set(method, value)
                            }
                          ],
                          [
                            '1',
                            {
                              store: new Map([
                                [
                                  'loader',
                                  'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\sass-loader\\dist\\cjs.js'
                                ],
                                [
                                  'options',
                                  {
                                    sourceMap: true,
                                    implementation: {
                                      load: function () { /* omitted long function */ },
                                      compile: function () {
                                        return _call(f, Array.prototype.slice.apply(arguments));
                                      },
                                      compileString: function () {
                                        return _call(f, Array.prototype.slice.apply(arguments));
                                      },
                                      compileAsync: function () {
                                        return _call(f, Array.prototype.slice.apply(arguments));
                                      },
                                      compileStringAsync: function () {
                                        return _call(f, Array.prototype.slice.apply(arguments));
                                      },
                                      initCompiler: function () {
                                        return _call(f, Array.prototype.slice.apply(arguments));
                                      },
                                      initAsyncCompiler: function () {
                                        return _call(f, Array.prototype.slice.apply(arguments));
                                      },
                                      Compiler: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      AsyncCompiler: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      Value: function Value0() {
                                      },
                                      SassBoolean: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      SassArgumentList: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      SassCalculation: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      CalculationOperation: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      CalculationInterpolation: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      SassColor: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      SassFunction: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      SassMixin: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      SassList: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      SassMap: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      SassNumber: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      SassString: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      sassNull: {},
                                      sassTrue: {
                                        value: true
                                      },
                                      sassFalse: {
                                        value: false
                                      },
                                      Exception: function () { /* omitted long function */ },
                                      Logger: {
                                        silent: {
                                          warn: function () {
                                            return _call(f, Array.prototype.slice.apply(arguments));
                                          },
                                          debug: function () {
                                            return _call(f, Array.prototype.slice.apply(arguments));
                                          }
                                        }
                                      },
                                      NodePackageImporter: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      deprecations: {
                                        'call-string': {
                                          id: 'call-string',
                                          status: 'active',
                                          description: 'Passing a string directly to meta.call().',
                                          deprecatedIn: {
                                            major: 0,
                                            minor: 0,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '0.0.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        elseif: {
                                          id: 'elseif',
                                          status: 'active',
                                          description: '@elseif.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 3,
                                            patch: 2,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.3.2'
                                          },
                                          obsoleteIn: null
                                        },
                                        'moz-document': {
                                          id: 'moz-document',
                                          status: 'active',
                                          description: '@-moz-document.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 7,
                                            patch: 2,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.7.2'
                                          },
                                          obsoleteIn: null
                                        },
                                        'relative-canonical': {
                                          id: 'relative-canonical',
                                          status: 'active',
                                          description: 'Imports using relative canonical URLs.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 14,
                                            patch: 2,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.14.2'
                                          },
                                          obsoleteIn: null
                                        },
                                        'new-global': {
                                          id: 'new-global',
                                          status: 'active',
                                          description: 'Declaring new variables with !global.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 17,
                                            patch: 2,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.17.2'
                                          },
                                          obsoleteIn: null
                                        },
                                        'color-module-compat': {
                                          id: 'color-module-compat',
                                          status: 'active',
                                          description: 'Using color module functions in place of plain CSS functions.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 23,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.23.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'slash-div': {
                                          id: 'slash-div',
                                          status: 'active',
                                          description: '/ operator for division.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 33,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.33.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'bogus-combinators': {
                                          id: 'bogus-combinators',
                                          status: 'active',
                                          description: 'Leading, trailing, and repeated combinators.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 54,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.54.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'strict-unary': {
                                          id: 'strict-unary',
                                          status: 'active',
                                          description: 'Ambiguous + and - operators.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 55,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.55.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'function-units': {
                                          id: 'function-units',
                                          status: 'active',
                                          description: 'Passing invalid units to built-in functions.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 56,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.56.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'duplicate-var-flags': {
                                          id: 'duplicate-var-flags',
                                          status: 'active',
                                          description: 'Using !default or !global multiple times for one variable.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 62,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.62.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'null-alpha': {
                                          id: 'null-alpha',
                                          status: 'active',
                                          description: 'Passing null as alpha in the JS API.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 62,
                                            patch: 3,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.62.3'
                                          },
                                          obsoleteIn: null
                                        },
                                        'abs-percent': {
                                          id: 'abs-percent',
                                          status: 'active',
                                          description: 'Passing percentages to the Sass abs() function.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 65,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.65.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'fs-importer-cwd': {
                                          id: 'fs-importer-cwd',
                                          status: 'active',
                                          description: 'Using the current working directory as an implicit load path.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 73,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.73.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'css-function-mixin': {
                                          id: 'css-function-mixin',
                                          status: 'obsolete',
                                          description: 'Function and mixin names beginning with --.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 76,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.76.0'
                                          },
                                          obsoleteIn: {
                                            major: 1,
                                            minor: 94,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.94.0'
                                          }
                                        },
                                        'mixed-decls': {
                                          id: 'mixed-decls',
                                          status: 'obsolete',
                                          description: 'Declarations after or between nested rules.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 77,
                                            patch: 7,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.77.7'
                                          },
                                          obsoleteIn: {
                                            major: 1,
                                            minor: 92,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.92.0'
                                          }
                                        },
                                        'feature-exists': {
                                          id: 'feature-exists',
                                          status: 'active',
                                          description: 'meta.feature-exists',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 78,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.78.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'color-4-api': {
                                          id: 'color-4-api',
                                          status: 'active',
                                          description: 'Certain uses of built-in sass:color functions.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 79,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.79.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'color-functions': {
                                          id: 'color-functions',
                                          status: 'active',
                                          description: 'Using global color functions instead of sass:color.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 79,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.79.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'legacy-js-api': {
                                          id: 'legacy-js-api',
                                          status: 'active',
                                          description: 'Legacy JS API.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 79,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.79.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'import': {
                                          id: 'import',
                                          status: 'active',
                                          description: '@import rules.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 80,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.80.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'global-builtin': {
                                          id: 'global-builtin',
                                          status: 'active',
                                          description: 'Global built-in functions that are available in sass: modules.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 80,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.80.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'type-function': {
                                          id: 'type-function',
                                          status: 'obsolete',
                                          description: 'Functions named "type".',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 86,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.86.0'
                                          },
                                          obsoleteIn: {
                                            major: 1,
                                            minor: 92,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.92.0'
                                          }
                                        },
                                        'compile-string-relative-url': {
                                          id: 'compile-string-relative-url',
                                          status: 'active',
                                          description: 'Passing a relative url to compileString().',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 88,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.88.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'misplaced-rest': {
                                          id: 'misplaced-rest',
                                          status: 'active',
                                          description: 'A rest parameter before a positional or named parameter.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 91,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.91.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'with-private': {
                                          id: 'with-private',
                                          status: 'active',
                                          description: 'Configuring private variables in @use, @forward, or load-css().',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 92,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.92.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'if-function': {
                                          id: 'if-function',
                                          status: 'active',
                                          description: 'The Sass if($condition, $if-true, $if-false) function.',
                                          deprecatedIn: {
                                            major: 1,
                                            minor: 95,
                                            patch: 0,
                                            preRelease: [],
                                            build: [],
                                            _version$_text: '1.95.0'
                                          },
                                          obsoleteIn: null
                                        },
                                        'user-authored': {
                                          id: 'user-authored',
                                          status: 'user',
                                          description: null,
                                          deprecatedIn: null,
                                          obsoleteIn: null
                                        }
                                      },
                                      Version: function () {
                                        return _call(f, this, Array.prototype.slice.apply(arguments));
                                      },
                                      loadParserExports_: function () {
                                        return _call(f, Array.prototype.slice.apply(arguments));
                                      },
                                      info: 'dart-sass\t1.98.0\t(Sass Compiler)\t[Dart]\ndart2js\t3.11.2\t(Dart Compiler)\t[Dart]',
                                      render: function () {
                                        return _call(f, Array.prototype.slice.apply(arguments));
                                      },
                                      renderSync: function () {
                                        return _call(f, Array.prototype.slice.apply(arguments));
                                      },
                                      types: {
                                        Boolean: function () {
                                          return _call(f, this, Array.prototype.slice.apply(arguments));
                                        },
                                        Color: function () {
                                          return _call(f, this, Array.prototype.slice.apply(arguments));
                                        },
                                        List: function () {
                                          return _call(f, this, Array.prototype.slice.apply(arguments));
                                        },
                                        Map: function () {
                                          return _call(f, this, Array.prototype.slice.apply(arguments));
                                        },
                                        Null: function () {
                                          return _call(f, this, Array.prototype.slice.apply(arguments));
                                        },
                                        Number: function () {
                                          return _call(f, this, Array.prototype.slice.apply(arguments));
                                        },
                                        String: function () {
                                          return _call(f, this, Array.prototype.slice.apply(arguments));
                                        },
                                        Error: function Error() { [native code] }
                                      },
                                      NULL: {},
                                      TRUE: {
                                        value: true
                                      },
                                      FALSE: {
                                        value: false
                                      },
                                      cli_pkg_main_0_: function () {
                                        return _call(f, Array.prototype.slice.apply(arguments));
                                      }
                                    },
                                    sassOptions: {
                                      outputStyle: 'expanded',
                                      silenceDeprecations: [
                                        'legacy-js-api'
                                      ],
                                      importer: function () { /* omitted long function */ }
                                    }
                                  }
                                ]
                              ]),
                              name: '1',
                              shorthands: [
                                'loader',
                                'options'
                              ],
                              loader: (value) => this.set(method, value),
                              options: (value) => this.set(method, value)
                            }
                          ]
                        ])
                      },
                      include: {
                        store: new Set([])
                      },
                      exclude: {
                        store: new Set([])
                      },
                      rules: {
                        store: new Map([])
                      },
                      oneOfs: {
                        store: new Map([])
                      },
                      resolve: {
                        store: new Map([]),
                        alias: {
                          store: new Map([])
                        },
                        aliasFields: {
                          store: new Set([])
                        },
                        descriptionFiles: {
                          store: new Set([])
                        },
                        extensions: {
                          store: new Set([])
                        },
                        mainFields: {
                          store: new Set([])
                        },
                        mainFiles: {
                          store: new Set([])
                        },
                        modules: {
                          store: new Set([])
                        },
                        plugins: {
                          store: new Map([])
                        },
                        shorthands: [
                          'cachePredicate',
                          'cacheWithContext',
                          'concord',
                          'enforceExtension',
                          'enforceModuleExtension',
                          'symlinks',
                          'unsafeCache'
                        ],
                        cachePredicate: (value) => this.set(method, value),
                        cacheWithContext: (value) => this.set(method, value),
                        concord: (value) => this.set(method, value),
                        enforceExtension: (value) => this.set(method, value),
                        enforceModuleExtension: (value) => this.set(method, value),
                        symlinks: (value) => this.set(method, value),
                        unsafeCache: (value) => this.set(method, value)
                      },
                      shorthands: [
                        'enforce',
                        'issuer',
                        'parser',
                        'resource',
                        'resourceQuery',
                        'sideEffects',
                        'test',
                        'type'
                      ],
                      enforce: (value) => this.set(method, value),
                      issuer: (value) => this.set(method, value),
                      parser: (value) => this.set(method, value),
                      resource: (value) => this.set(method, value),
                      resourceQuery: (value) => this.set(method, value),
                      sideEffects: (value) => this.set(method, value),
                      test: (value) => this.set(method, value),
                      type: (value) => this.set(method, value)
                    }
                  ],
                  [
                    'less',
                    {
                      store: new Map([
                        [
                          'test',
                          /\.less$/
                        ]
                      ]),
                      name: 'less',
                      names: [
                        'less'
                      ],
                      ruleType: 'rule',
                      ruleTypes: [
                        'rule'
                      ],
                      uses: {
                        store: new Map([
                          [
                            '0',
                            {
                              store: new Map([
                                [
                                  'loader',
                                  'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\less-loader\\dist\\cjs.js'
                                ],
                                [
                                  'options',
                                  {}
                                ]
                              ]),
                              name: '0',
                              shorthands: [
                                'loader',
                                'options'
                              ],
                              loader: (value) => this.set(method, value),
                              options: (value) => this.set(method, value)
                            }
                          ]
                        ])
                      },
                      include: {
                        store: new Set([])
                      },
                      exclude: {
                        store: new Set([])
                      },
                      rules: {
                        store: new Map([])
                      },
                      oneOfs: {
                        store: new Map([])
                      },
                      resolve: {
                        store: new Map([]),
                        alias: {
                          store: new Map([])
                        },
                        aliasFields: {
                          store: new Set([])
                        },
                        descriptionFiles: {
                          store: new Set([])
                        },
                        extensions: {
                          store: new Set([])
                        },
                        mainFields: {
                          store: new Set([])
                        },
                        mainFiles: {
                          store: new Set([])
                        },
                        modules: {
                          store: new Set([])
                        },
                        plugins: {
                          store: new Map([])
                        },
                        shorthands: [
                          'cachePredicate',
                          'cacheWithContext',
                          'concord',
                          'enforceExtension',
                          'enforceModuleExtension',
                          'symlinks',
                          'unsafeCache'
                        ],
                        cachePredicate: (value) => this.set(method, value),
                        cacheWithContext: (value) => this.set(method, value),
                        concord: (value) => this.set(method, value),
                        enforceExtension: (value) => this.set(method, value),
                        enforceModuleExtension: (value) => this.set(method, value),
                        symlinks: (value) => this.set(method, value),
                        unsafeCache: (value) => this.set(method, value)
                      },
                      shorthands: [
                        'enforce',
                        'issuer',
                        'parser',
                        'resource',
                        'resourceQuery',
                        'sideEffects',
                        'test',
                        'type'
                      ],
                      enforce: (value) => this.set(method, value),
                      issuer: (value) => this.set(method, value),
                      parser: (value) => this.set(method, value),
                      resource: (value) => this.set(method, value),
                      resourceQuery: (value) => this.set(method, value),
                      sideEffects: (value) => this.set(method, value),
                      test: (value) => this.set(method, value),
                      type: (value) => this.set(method, value)
                    }
                  ],
                  [
                    'stylus',
                    {
                      store: new Map([
                        [
                          'test',
                          /\.styl(us)?$/
                        ]
                      ]),
                      name: 'stylus',
                      names: [
                        'stylus'
                      ],
                      ruleType: 'rule',
                      ruleTypes: [
                        'rule'
                      ],
                      uses: {
                        store: new Map([
                          [
                            '0',
                            {
                              store: new Map([
                                [
                                  'loader',
                                  'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\stylus-loader\\dist\\cjs.js'
                                ],
                                [
                                  'options',
                                  {}
                                ]
                              ]),
                              name: '0',
                              shorthands: [
                                'loader',
                                'options'
                              ],
                              loader: (value) => this.set(method, value),
                              options: (value) => this.set(method, value)
                            }
                          ]
                        ])
                      },
                      include: {
                        store: new Set([])
                      },
                      exclude: {
                        store: new Set([])
                      },
                      rules: {
                        store: new Map([])
                      },
                      oneOfs: {
                        store: new Map([])
                      },
                      resolve: {
                        store: new Map([]),
                        alias: {
                          store: new Map([])
                        },
                        aliasFields: {
                          store: new Set([])
                        },
                        descriptionFiles: {
                          store: new Set([])
                        },
                        extensions: {
                          store: new Set([])
                        },
                        mainFields: {
                          store: new Set([])
                        },
                        mainFiles: {
                          store: new Set([])
                        },
                        modules: {
                          store: new Set([])
                        },
                        plugins: {
                          store: new Map([])
                        },
                        shorthands: [
                          'cachePredicate',
                          'cacheWithContext',
                          'concord',
                          'enforceExtension',
                          'enforceModuleExtension',
                          'symlinks',
                          'unsafeCache'
                        ],
                        cachePredicate: (value) => this.set(method, value),
                        cacheWithContext: (value) => this.set(method, value),
                        concord: (value) => this.set(method, value),
                        enforceExtension: (value) => this.set(method, value),
                        enforceModuleExtension: (value) => this.set(method, value),
                        symlinks: (value) => this.set(method, value),
                        unsafeCache: (value) => this.set(method, value)
                      },
                      shorthands: [
                        'enforce',
                        'issuer',
                        'parser',
                        'resource',
                        'resourceQuery',
                        'sideEffects',
                        'test',
                        'type'
                      ],
                      enforce: (value) => this.set(method, value),
                      issuer: (value) => this.set(method, value),
                      parser: (value) => this.set(method, value),
                      resource: (value) => this.set(method, value),
                      resourceQuery: (value) => this.set(method, value),
                      sideEffects: (value) => this.set(method, value),
                      test: (value) => this.set(method, value),
                      type: (value) => this.set(method, value)
                    }
                  ],
                  [
                    'script',
                    {
                      store: new Map([
                        [
                          'test',
                          /\.m?[tj]sx?$/i
                        ]
                      ]),
                      name: 'script',
                      names: [
                        'script'
                      ],
                      ruleType: 'rule',
                      ruleTypes: [
                        'rule'
                      ],
                      uses: {
                        store: new Map([
                          [
                            'babelLoader',
                            {
                              store: new Map([
                                [
                                  'loader',
                                  'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\babel-loader\\lib\\index.js'
                                ],
                                [
                                  'options',
                                  {
                                    compact: false,
                                    plugins: [
                                      [
                                        {
                                          'default': function () { /* omitted long function */ }
                                        },
                                        {
                                          packageName: '@tarojs/taro',
                                          definition: {
                                            apis: {
                                              Behavior: '*',
                                              getEnv: '*',
                                              ENV_TYPE: '*',
                                              Link: '*',
                                              interceptors: '*',
                                              interceptorify: '*',
                                              Current: '*',
                                              options: '*',
                                              eventCenter: '*',
                                              Events: '*',
                                              preload: '*',
                                              taro: {},
                                              requirePlugin: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              initPxTransform: {
                                                object: '{ designWidth?: number; deviceRatio?: TDeviceRatio; baseFontSize?: number; unitPrecision?: number; targetUnit?: string; }',
                                                success: 'void'
                                              },
                                              pxTransform: {
                                                object: 'number',
                                                success: 'void',
                                                'return': '*'
                                              },
                                              canIUseWebp: {
                                                object: 'void',
                                                success: 'void',
                                                'return': 'boolean'
                                              },
                                              getAppInfo: {
                                                object: 'void',
                                                success: 'void',
                                                'return': '{ platform: string; taroVersion: string; designWidth: any; }'
                                              },
                                              createRewardedVideoAd: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              createInterstitialAd: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              stopFaceDetect: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              initFaceDetect: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              faceDetect: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getInferenceEnvInfo: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              createInferenceSession: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              isVKSupport: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              createVKSession: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getOpenUserInfo: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              tradePay: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getUserCryptoManager: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              setEnableDebug: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getRealtimeLogManager: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getLogManager: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              reportPerformance: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getPerformance: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              preloadWebview: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              preloadSkylineView: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              preloadAssets: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              openSystemBluetoothSetting: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              openAppAuthorizeSetting: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getWindowInfo: {
                                                object: 'void',
                                                success: 'void',
                                                'return': 'Result'
                                              },
                                              getSystemSetting: {
                                                object: 'void',
                                                success: 'void',
                                                'return': 'Result'
                                              },
                                              getDeviceInfo: {
                                                object: 'void',
                                                success: 'void',
                                                'return': 'Result'
                                              },
                                              getAppBaseInfo: {
                                                object: 'void',
                                                success: 'void',
                                                'return': 'Result'
                                              },
                                              getAppAuthorizeSetting: {
                                                object: 'void',
                                                success: 'void',
                                                'return': 'Result'
                                              },
                                              getSystemInfoSync: {
                                                object: 'void',
                                                success: 'void',
                                                'return': 'Result'
                                              },
                                              getSystemInfoAsync: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<Result>'
                                              },
                                              getSystemInfo: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<Result>'
                                              },
                                              getSkylineInfoSync: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getSkylineInfo: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getRendererUserAgent: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              updateWeChatApp: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getUpdateManager: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onUnhandledRejection: {
                                                callback: 'Result<T>'
                                              },
                                              onThemeChange: {
                                                callback: 'Result'
                                              },
                                              onPageNotFound: {
                                                callback: 'Result'
                                              },
                                              onLazyLoadError: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onError: {
                                                callback: 'string | ErrorEvent | Error'
                                              },
                                              onAudioInterruptionEnd: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onAudioInterruptionBegin: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onAppShow: {
                                                callback: 'CallbackResult'
                                              },
                                              onAppHide: {
                                                callback: 'CallbackResult'
                                              },
                                              offUnhandledRejection: {
                                                callback: 'Result<T>'
                                              },
                                              offThemeChange: {
                                                callback: 'Result'
                                              },
                                              offPageNotFound: {
                                                callback: 'Result'
                                              },
                                              offLazyLoadError: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offError: {
                                                callback: 'string | ErrorEvent | Error'
                                              },
                                              offAudioInterruptionEnd: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offAudioInterruptionBegin: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offAppShow: {
                                                callback: 'CallbackResult'
                                              },
                                              offAppHide: {
                                                callback: 'CallbackResult'
                                              },
                                              getLaunchOptionsSync: {
                                                object: 'void',
                                                success: 'void',
                                                'return': 'LaunchOptions'
                                              },
                                              getEnterOptionsSync: {
                                                object: 'void',
                                                success: 'void',
                                                'return': 'EnterOptions'
                                              },
                                              env: {},
                                              arrayBufferToBase64: '*',
                                              base64ToArrayBuffer: '*',
                                              createCanvasContext: {
                                                object: 'string',
                                                success: 'void',
                                                'return': 'CanvasContext'
                                              },
                                              canvasToTempFilePath: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<SuccessCallbackResult>'
                                              },
                                              canvasPutImageData: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              canvasGetImageData: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<SuccessCallbackResult>'
                                              },
                                              createOffscreenCanvas: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              reportMonitor: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              reportAnalytics: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              reportEvent: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getExptInfoSync: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              stopAccelerometer: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              startAccelerometer: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              onAccelerometerChange: {
                                                callback: 'Result'
                                              },
                                              offAccelerometerChange: {
                                                callback: 'Result'
                                              },
                                              checkIsOpenAccessibility: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getBatteryInfoSync: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getBatteryInfo: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<SuccessCallbackResult>'
                                              },
                                              stopBluetoothDevicesDiscovery: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              startBluetoothDevicesDiscovery: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              openBluetoothAdapter: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onBluetoothDeviceFound: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onBluetoothAdapterStateChange: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offBluetoothDeviceFound: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offBluetoothAdapterStateChange: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              makeBluetoothPair: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              isBluetoothDevicePaired: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getConnectedBluetoothDevices: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getBluetoothDevices: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getBluetoothAdapterState: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              closeBluetoothAdapter: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              writeBLECharacteristicValue: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              setBLEMTU: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              readBLECharacteristicValue: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onBLEMTUChange: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onBLEConnectionStateChange: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onBLECharacteristicValueChange: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offBLEMTUChange: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offBLEConnectionStateChange: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offBLECharacteristicValueChange: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              notifyBLECharacteristicValueChange: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getBLEMTU: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getBLEDeviceServices: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getBLEDeviceRSSI: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getBLEDeviceCharacteristics: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              createBLEConnection: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              closeBLEConnection: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onBLEPeripheralConnectionStateChanged: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offBLEPeripheralConnectionStateChanged: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              createBLEPeripheralServer: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              addPhoneRepeatCalendar: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              addPhoneCalendar: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              setClipboardData: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<Promised>'
                                              },
                                              getClipboardData: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<Promised>'
                                              },
                                              stopCompass: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              startCompass: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              onCompassChange: {
                                                callback: 'OnCompassChangeCallbackResult'
                                              },
                                              offCompassChange: {
                                                callback: 'OnCompassChangeCallbackResult'
                                              },
                                              chooseContact: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              addPhoneContact: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getRandomValues: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              stopGyroscope: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              startGyroscope: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onGyroscopeChange: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offGyroscopeChange: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              stopBeaconDiscovery: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              startBeaconDiscovery: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onBeaconUpdate: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onBeaconServiceChange: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offBeaconUpdate: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offBeaconServiceChange: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getBeacons: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onKeyboardHeightChange: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offKeyboardHeightChange: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              hideKeyboard: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getSelectedTextRange: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onMemoryWarning: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offMemoryWarning: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              stopDeviceMotionListening: {
                                                object: 'Option',
                                                success: 'void'
                                              },
                                              startDeviceMotionListening: {
                                                object: 'Option',
                                                success: 'void'
                                              },
                                              onDeviceMotionChange: {
                                                callback: 'CallbackResult'
                                              },
                                              offDeviceMotionChange: {
                                                callback: 'CallbackResult'
                                              },
                                              getNetworkType: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<SuccessCallbackResult>'
                                              },
                                              onNetworkWeakChange: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onNetworkStatusChange: {
                                                callback: 'CallbackResult'
                                              },
                                              offNetworkWeakChange: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offNetworkStatusChange: {
                                                callback: 'CallbackResult'
                                              },
                                              getLocalIPAddress: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              stopHCE: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              startHCE: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              sendHCEMessage: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onHCEMessage: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offHCEMessage: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getNFCAdapter: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getHCEState: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              makePhoneCall: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              scanCode: {
                                                object: 'Partial<{ needResult: number; }>',
                                                success: 'void',
                                                'return': 'Promise<any>'
                                              },
                                              setVisualEffectOnCapture: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              setScreenBrightness: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              setKeepScreenOn: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onUserCaptureScreen: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offUserCaptureScreen: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getScreenBrightness: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onScreenRecordingStateChanged: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offScreenRecordingStateChanged: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getScreenRecordingState: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              sendSms: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              vibrateShort: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              vibrateLong: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              stopWifi: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              startWifi: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              setWifiList: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onWifiConnectedWithPartialInfo: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onWifiConnected: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onGetWifiList: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offWifiConnectedWithPartialInfo: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offWifiConnected: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offGetWifiList: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getWifiList: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getConnectedWifi: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              connectWifi: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getExtConfigSync: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getExtConfig: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              saveFileToDisk: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              saveFile: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              removeSavedFile: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              openDocument: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getSavedFileList: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getSavedFileInfo: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getFileSystemManager: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getFileInfo: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getApp: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Instance<T>'
                                              },
                                              getCurrentInstance: {
                                                object: 'void',
                                                success: 'void',
                                                'return': 'Current'
                                              },
                                              getLocation: {
                                                object: 'Partial<Option>',
                                                success: 'void',
                                                'return': 'Promise<SuccessCallbackResult>'
                                              },
                                              css_248z: {},
                                              chooseLocation: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<SuccessCallbackResult>'
                                              },
                                              onLocationChange: '*',
                                              offLocationChange: '*',
                                              onLocationChangeError: '*',
                                              offLocationChangeError: '*',
                                              stopLocationUpdate: {
                                                object: 'Partial<Option>',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              startLocationUpdate: {
                                                object: 'Partial<Option>',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              startLocationUpdateBackground: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              openLocation: {
                                                object: 'Partial<{ scale: number; }>',
                                                success: 'void',
                                                'return': 'Promise<any>'
                                              },
                                              choosePoi: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getFuzzyLocation: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              stopVoice: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              setInnerAudioOption: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              playVoice: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              pauseVoice: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getAvailableAudioSources: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              createWebAudioContext: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              createMediaAudioPlayer: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              createInnerAudioContext: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'InnerAudioContext'
                                              },
                                              createAudioContext: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              stopBackgroundAudio: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              seekBackgroundAudio: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              playBackgroundAudio: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              pauseBackgroundAudio: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onBackgroundAudioStop: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onBackgroundAudioPlay: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onBackgroundAudioPause: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getBackgroundAudioPlayerState: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getBackgroundAudioManager: {
                                                object: 'void',
                                                success: 'void',
                                                'return': 'BackgroundAudioManager'
                                              },
                                              createCameraContext: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              saveImageToPhotosAlbum: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              getImageInfo: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<SuccessCallbackResult>'
                                              },
                                              previewImage: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              chooseImage: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<SuccessCallbackResult>'
                                              },
                                              previewMedia: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              compressImage: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              chooseMessageFile: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              editImage: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              cropImage: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              createLivePusherContext: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              createLivePlayerContext: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              createMapContext: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              createMediaRecorder: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              stopRecord: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              startRecord: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getRecorderManager: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              saveVideoToPhotosAlbum: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              getVideoInfo: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<SuccessCallbackResult>'
                                              },
                                              chooseMedia: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<SuccessCallbackResult>'
                                              },
                                              chooseVideo: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<SuccessCallbackResult>'
                                              },
                                              openVideoEditor: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              createVideoContext: {
                                                object: 'string',
                                                success: 'void',
                                                'return': 'VideoContext'
                                              },
                                              compressVideo: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              createVideoDecoder: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              createMediaContainer: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              updateVoIPChatMuteConfig: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              subscribeVoIPVideoMembers: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              setEnable1v1Chat: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onVoIPVideoMembersChanged: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onVoIPChatStateChanged: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onVoIPChatSpeakersChanged: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onVoIPChatMembersChanged: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onVoIPChatInterrupted: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offVoIPChatSpeakersChanged: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offVoIPVideoMembersChanged: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offVoIPChatStateChanged: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offVoIPChatMembersChanged: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offVoIPChatInterrupted: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              joinVoIPChat: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              join1v1Chat: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              exitVoIPChat: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              openEmbeddedMiniProgram: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              navigateToMiniProgram: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              navigateBackMiniProgram: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              exitMiniProgram: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              openBusinessView: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              downloadFile: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'DownloadTaskPromise'
                                              },
                                              stopLocalServiceDiscovery: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              startLocalServiceDiscovery: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onLocalServiceResolveFail: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onLocalServiceLost: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onLocalServiceFound: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onLocalServiceDiscoveryStop: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offLocalServiceResolveFail: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offLocalServiceLost: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offLocalServiceFound: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offLocalServiceDiscoveryStop: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              request: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'RequestTask<T>'
                                              },
                                              addInterceptor: '*',
                                              cleanInterceptors: '*',
                                              createTCPSocket: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              createUDPSocket: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              uploadFile: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'UploadTaskPromise'
                                              },
                                              sendSocketMessage: '*',
                                              onSocketOpen: '*',
                                              onSocketMessage: '*',
                                              onSocketError: '*',
                                              onSocketClose: '*',
                                              connectSocket: '*',
                                              closeSocket: '*',
                                              getAccountInfoSync: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              chooseAddress: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              authorizeForMiniProgram: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              authorize: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              openCard: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              addCard: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              reserveChannelsLive: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              openChannelsUserProfile: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              openChannelsLive: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              openChannelsEvent: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              openChannelsActivity: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getChannelsShareKey: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getChannelsLiveNoticeInfo: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getChannelsLiveInfo: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              openCustomerServiceChat: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              requestDeviceVoIP: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getDeviceVoIPList: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              checkIsSupportFacialRecognition: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              startFacialRecognitionVerify: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              startFacialRecognitionVerifyAndUploadVideo: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              faceVerifyForPay: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              addVideoToFavorites: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              addFileToFavorites: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getGroupEnterInfo: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              chooseInvoiceTitle: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              chooseInvoice: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              chooseLicensePlate: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              pluginLogin: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              login: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              checkSession: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              checkIsAddedToMyMiniProgram: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              requirePrivacyAuthorize: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              openPrivacyContract: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onNeedPrivacyAuthorization: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getPrivacySetting: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              showRedPackage: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              openSetting: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getSetting: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              startSoterAuthentication: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              checkIsSupportSoterAuthentication: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              checkIsSoterEnrolledInDevice: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              requestSubscribeMessage: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              requestSubscribeDeviceMessage: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getUserProfile: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getUserInfo: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              shareToWeRun: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getWeRunData: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              requestPayment: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              requestPluginPayment: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              requestOrderPayment: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              openQzonePublish: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getQQRunData: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              setOfficialDress: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              setCustomDress: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              updateQQApp: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              addRecentColorSign: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getGuildInfo: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              applyAddToMyApps: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              isAddedToMyApps: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              router: {},
                                              updateShareMenu: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              showShareMenu: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              showShareImageMenu: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              shareVideoMessage: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              shareFileMessage: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onCopyUrl: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              offCopyUrl: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              hideShareMenu: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getShareInfo: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              authPrivateMessage: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              setBackgroundFetchToken: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onBackgroundFetchData: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getBackgroundFetchToken: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getBackgroundFetchData: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              createCacheManager: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              setStorageSync: {
                                                object: 'string',
                                                success: 'void'
                                              },
                                              setStorage: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              revokeBufferURL: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              removeStorageSync: {
                                                object: 'string',
                                                success: 'void'
                                              },
                                              removeStorage: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              getStorageSync: {
                                                object: '*',
                                                success: 'void',
                                                'return': '*'
                                              },
                                              getStorageInfoSync: {
                                                object: 'void',
                                                success: 'void',
                                                'return': 'Option'
                                              },
                                              getStorageInfo: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              getStorage: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<SuccessCallbackResult<T>>'
                                              },
                                              createBufferURL: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              clearStorageSync: {
                                                object: 'void',
                                                success: 'void'
                                              },
                                              clearStorage: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              batchSetStorageSync: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              batchSetStorage: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              batchGetStorageSync: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              batchGetStorage: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              setPageInfo: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              ocrIdCard: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              ocrBankCard: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              ocrDrivingLicense: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              ocrVehicleLicense: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              textReview: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              textToAudio: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              imageAudit: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              advancedGeneralIdentify: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              objectDetectIdentify: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              carClassify: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              dishClassify: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              logoClassify: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              animalClassify: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              plantClassify: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getSwanId: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              requestPolymerPayment: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              navigateToSmartGameProgram: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              navigateToSmartProgram: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              navigateBackSmartProgram: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              preloadSubPackage: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              createAnimation: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Animation'
                                              },
                                              worklet: '*',
                                              setBackgroundTextStyle: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              setBackgroundColor: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              nextTick: {
                                                callback: 'any[]'
                                              },
                                              loadFontFace: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              showToast: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              hideToast: {
                                                object: 'Option',
                                                success: 'void'
                                              },
                                              showLoading: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              hideLoading: {
                                                object: 'Option',
                                                success: 'void'
                                              },
                                              showModal: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<SuccessCallbackResult>'
                                              },
                                              showActionSheet: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<SuccessCallbackResult>'
                                              },
                                              enableAlertBeforeUnload: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              disableAlertBeforeUnload: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              getMenuButtonBoundingClientRect: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              showNavigationBarLoading: '*',
                                              setNavigationBarTitle: '*',
                                              setNavigationBarColor: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              hideNavigationBarLoading: '*',
                                              hideHomeButton: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              startPullDownRefresh: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              stopPullDownRefresh: {
                                                object: 'Option',
                                                success: 'void'
                                              },
                                              pageScrollTo: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              setTopBarText: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              initTabBarApis: '*',
                                              showTabBarRedDot: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              showTabBar: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              setTabBarStyle: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              setTabBarItem: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              setTabBarBadge: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              removeTabBarBadge: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              hideTabBarRedDot: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              hideTabBar: {
                                                object: 'Option',
                                                success: 'void',
                                                'return': 'Promise<CallbackResult>'
                                              },
                                              setWindowSize: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              onWindowResize: {
                                                callback: 'CallbackResult'
                                              },
                                              offWindowResize: {
                                                callback: 'CallbackResult'
                                              },
                                              checkIsPictureInPictureActive: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              createWorker: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                                              },
                                              createSelectorQuery: {
                                                object: 'void',
                                                success: 'void',
                                                'return': 'SelectorQuery'
                                              },
                                              createIntersectionObserver: {
                                                object: '*',
                                                success: 'void',
                                                'return': 'IntersectionObserver'
                                              },
                                              createMediaQueryObserver: {
                                                object: 'void',
                                                success: 'void',
                                                'return': 'MediaQueryObserver'
                                              }
                                            },
                                            components: {
                                              ad: {},
                                              'ad-custom': {},
                                              'animation-video': {},
                                              'animation-view': {},
                                              'ar-camera': {},
                                              audio: {
                                                autoplay: 'boolean',
                                                controls: 'boolean',
                                                loop: 'boolean',
                                                muted: 'boolean',
                                                nativeProps: '*',
                                                src: 'string'
                                              },
                                              'aweme-data': {},
                                              block: {},
                                              button: {
                                                disabled: 'boolean',
                                                formType: '"submit" | "reset"',
                                                hoverClass: 'string',
                                                hoverStartTime: 'number',
                                                hoverStayTime: 'number',
                                                loading: 'boolean',
                                                plain: 'boolean',
                                                size: 'string',
                                                type: 'string'
                                              },
                                              camera: {},
                                              canvas: {
                                                canvasId: 'string',
                                                height: 'string',
                                                nativeProps: '*',
                                                width: 'string'
                                              },
                                              'channel-live': {},
                                              'channel-video': {},
                                              checkbox: {
                                                checked: 'boolean',
                                                color: 'string',
                                                disabled: 'boolean',
                                                id: 'string',
                                                name: 'string',
                                                nativeProps: '*',
                                                value: 'string | number'
                                              },
                                              'checkbox-group': {
                                                name: '*'
                                              },
                                              'comment-detail': {},
                                              'comment-list': {},
                                              'contact-button': {},
                                              'cover-image': {
                                                nativeProps: '*',
                                                src: 'string'
                                              },
                                              'cover-view': {
                                                animation: 'string',
                                                hoverClass: 'string',
                                                hoverStartTime: 'number',
                                                hoverStayTime: 'number'
                                              },
                                              'custom-wrapper': {},
                                              'double-tap-gesture-handler': {},
                                              'draggable-sheet': {},
                                              editor: {},
                                              'follow-swan': {},
                                              'force-press-gesture-handler': {},
                                              form: {},
                                              'functional-page-navigator': {},
                                              'grid-builder': {},
                                              'grid-view': {},
                                              'horizontal-drag-gesture-handler': {},
                                              icon: {
                                                color: 'string',
                                                size: 'string | number',
                                                type: 'Type'
                                              },
                                              image: {
                                                lazyLoad: 'boolean',
                                                mode: 'Mode',
                                                nativeProps: '*',
                                                src: 'string'
                                              },
                                              'inline-payment-panel': {},
                                              input: {
                                                autoFocus: 'boolean',
                                                confirmType: 'string',
                                                disabled: 'boolean',
                                                focus: '() => Promise<void>',
                                                maxlength: 'number',
                                                name: 'string',
                                                nativeProps: '*',
                                                password: 'boolean',
                                                placeholder: 'string',
                                                readonly: 'boolean',
                                                type: 'string',
                                                value: 'string'
                                              },
                                              'keyboard-accessory': {},
                                              label: {
                                                'for': 'string'
                                              },
                                              lifestyle: {},
                                              like: {},
                                              'list-builder': {},
                                              'list-view': {},
                                              'live-player': {},
                                              'live-pusher': {},
                                              login: {},
                                              'long-press-gesture-handler': {},
                                              lottie: {},
                                              map: {
                                                circles: 'MapProps.circle[]',
                                                enable3D: 'boolean',
                                                enableAutoMaxOverlooking: 'boolean',
                                                enableBuilding: 'boolean',
                                                enableOverlooking: 'boolean',
                                                enableRotate: 'boolean',
                                                enableSatellite: 'boolean',
                                                enableScroll: 'boolean',
                                                enableTraffic: 'boolean',
                                                enableZoom: 'boolean',
                                                height: 'string',
                                                latitude: 'number',
                                                layerStyle: 'number',
                                                longitude: 'number',
                                                markers: 'MapProps.marker[]',
                                                maxScale: 'number',
                                                minScale: 'number',
                                                polygons: 'MapProps.polygon[]',
                                                polyline: 'MapProps.polyline[]',
                                                rotate: 'number',
                                                scale: 'number',
                                                showCompass: 'boolean',
                                                showScale: 'boolean',
                                                skew: 'number',
                                                subkey: 'string',
                                                width: 'string'
                                              },
                                              'match-media': {},
                                              'movable-area': {
                                                scaleArea: 'boolean'
                                              },
                                              'movable-view': {
                                                animation: 'boolean',
                                                damping: 'number',
                                                direction: '"all" | "vertical" | "horizontal" | "none"',
                                                disabled: 'boolean',
                                                endScale: '() => Promise<void>',
                                                friction: 'number',
                                                inertia: 'boolean',
                                                outOfBounds: 'boolean',
                                                scale: 'boolean',
                                                scaleMax: 'number',
                                                scaleMin: 'number',
                                                scaleValue: 'number',
                                                setParent: '({ element, area }: { element: HTMLElement; area: { width: number; height: number; }; }) => Promise<void>',
                                                setScale: '(scale: number) => Promise<void>',
                                                x: 'string | number',
                                                y: 'string | number'
                                              },
                                              'native-slot': {},
                                              'navigation-bar': {},
                                              navigator: {
                                                delta: 'number',
                                                hoverClass: 'string',
                                                isHover: 'boolean',
                                                openType: 'string',
                                                url: 'string'
                                              },
                                              'nested-scroll-body': {},
                                              'nested-scroll-header': {},
                                              'official-account': {},
                                              'open-container': {},
                                              'open-data': {},
                                              'page-container': {},
                                              'page-meta': {},
                                              'pan-gesture-handler': {},
                                              picker: {
                                                disabled: 'boolean',
                                                end: 'string',
                                                fields: 'Fields',
                                                mode: 'Mode',
                                                name: 'string',
                                                range: 'any[]',
                                                rangeKey: 'string',
                                                start: 'string',
                                                textProps: 'PickerText',
                                                value: 'PickerValue'
                                              },
                                              'picker-view-column': {
                                                col: 'string',
                                                initialPosition: 'string',
                                                paddingVertical: 'number'
                                              },
                                              'picker-view': {
                                                indicatorClass: 'string',
                                                indicatorStyle: 'string',
                                                maskClass: 'string',
                                                maskStyle: 'string',
                                                value: 'number[]'
                                              },
                                              progress: {
                                                active: 'boolean',
                                                activeColor: 'string',
                                                backgroundColor: 'string',
                                                borderRadius: 'string | number',
                                                fontSize: 'string | number',
                                                percent: 'number',
                                                showInfo: 'boolean',
                                                strokeWidth: 'string | number'
                                              },
                                              'pull-to-refresh': {
                                                damping: 'number',
                                                distanceToRefresh: 'number',
                                                indicator: '{ activate: string; deactivate: string; release: string; finish: string; }',
                                                prefixCls: 'string'
                                              },
                                              radio: {
                                                checked: 'boolean',
                                                disabled: 'boolean',
                                                id: 'string',
                                                name: 'string',
                                                nativeProps: '*',
                                                value: 'string'
                                              },
                                              'radio-group': {
                                                name: '*'
                                              },
                                              'rich-text': {
                                                nodes: 'Nodes',
                                                selectable: 'boolean',
                                                space: 'string | number | symbol',
                                                userSelect: 'boolean'
                                              },
                                              'root-portal': {},
                                              'rtc-room': {},
                                              'rtc-room-item': {},
                                              'scale-gesture-handler': {},
                                              script: {},
                                              'scroll-view': {
                                                animated: 'boolean',
                                                enhanced: 'boolean',
                                                lowerThreshold: 'string | number',
                                                mpScrollIntoView: 'string',
                                                mpScrollIntoViewAlignment: '"center" | "start" | "end" | "nearest"',
                                                mpScrollIntoViewMethod: '(selector: string) => Promise<void>',
                                                mpScrollLeft: 'string | number',
                                                mpScrollToMethod: '(object: Option) => Promise<void>',
                                                mpScrollTop: 'string | number',
                                                scrollX: 'boolean',
                                                scrollY: 'boolean',
                                                showScrollbar: 'boolean',
                                                upperThreshold: 'string | number'
                                              },
                                              'share-element': {},
                                              slider: {
                                                activeColor: 'string',
                                                backgroundColor: 'string',
                                                blockColor: 'string',
                                                blockSize: 'number',
                                                disabled: 'boolean',
                                                max: 'number',
                                                min: 'number',
                                                name: 'string',
                                                showValue: 'boolean',
                                                step: 'number',
                                                value: 'number'
                                              },
                                              slot: {},
                                              snapshot: {},
                                              span: {},
                                              'sticky-header': {},
                                              'sticky-section': {},
                                              swiper: {
                                                autoplay: 'boolean',
                                                circular: 'boolean',
                                                current: 'number',
                                                currentItemId: 'string',
                                                displayMultipleItems: 'number',
                                                duration: 'number',
                                                effectsProps: 'Record<string, any>',
                                                full: 'boolean',
                                                indicatorActiveColor: 'string',
                                                indicatorColor: 'string',
                                                indicatorDots: 'boolean',
                                                interval: 'number',
                                                nextMargin: 'string',
                                                previousMargin: 'string',
                                                vertical: 'boolean',
                                                zoom: 'boolean'
                                              },
                                              'swiper-item': {
                                                itemId: 'string'
                                              },
                                              'switch': {
                                                checked: 'boolean',
                                                color: 'string',
                                                disabled: 'boolean',
                                                name: 'string',
                                                nativeProps: '*',
                                                type: 'string'
                                              },
                                              'tab-item': {},
                                              tabs: {},
                                              'tap-gesture-handler': {},
                                              text: {
                                                numberOfLines: 'number',
                                                selectable: 'boolean',
                                                space: 'string | number | symbol',
                                                userSelect: 'boolean'
                                              },
                                              textarea: {
                                                autoFocus: 'boolean',
                                                autoHeight: 'boolean',
                                                disabled: 'boolean',
                                                focus: '() => Promise<void>',
                                                maxlength: 'number',
                                                name: 'string',
                                                nativeProps: '*',
                                                placeholder: 'string',
                                                value: 'string'
                                              },
                                              'vertical-drag-gesture-handler': {},
                                              video: {
                                                autoplay: 'boolean',
                                                controls: 'boolean',
                                                danmuBtn: 'boolean',
                                                danmuList: '[]',
                                                duration: 'number',
                                                enableDanmu: 'boolean',
                                                enablePlayGesture: 'boolean',
                                                enableProgressGesture: 'boolean',
                                                exitFullScreen: '() => Promise<void>',
                                                getHlsObject: '() => Promise<HLS>',
                                                initialTime: 'number',
                                                loop: 'boolean',
                                                muted: 'boolean',
                                                nativeProps: '*',
                                                objectFit: '"contain" | "fill" | "cover"',
                                                pause: '() => Promise<void>',
                                                play: '() => Promise<void>',
                                                poster: 'string',
                                                requestFullScreen: '() => Promise<void>',
                                                seek: '(position: number) => Promise<void>',
                                                showCenterPlayBtn: 'boolean',
                                                showFullscreenBtn: 'boolean',
                                                showMuteBtn: 'boolean',
                                                showPlayBtn: 'boolean',
                                                showProgress: 'boolean',
                                                src: 'string',
                                                stop: '() => Promise<void>',
                                                vslideGesture: 'boolean',
                                                vslideGestureInFullscreen: 'boolean'
                                              },
                                              view: {
                                                animation: 'string',
                                                hoverClass: 'string',
                                                hoverStartTime: 'number',
                                                hoverStayTime: 'number'
                                              },
                                              'voip-room': {},
                                              'web-view': {
                                                src: 'string'
                                              }
                                            }
                                          }
                                        }
                                      ]
                                    ]
                                  }
                                ]
                              ]),
                              name: 'babelLoader',
                              shorthands: [
                                'loader',
                                'options'
                              ],
                              loader: (value) => this.set(method, value),
                              options: (value) => this.set(method, value)
                            }
                          ]
                        ])
                      },
                      include: {
                        store: new Set([
                          'C:\\Code\\FamilyClaw\\apps\\user-app\\src',
                          filename => /(?<=node_modules[\\/]).*taro/.test(filename)
                        ])
                      },
                      exclude: {
                        store: new Set([])
                      },
                      rules: {
                        store: new Map([])
                      },
                      oneOfs: {
                        store: new Map([])
                      },
                      resolve: {
                        store: new Map([]),
                        alias: {
                          store: new Map([])
                        },
                        aliasFields: {
                          store: new Set([])
                        },
                        descriptionFiles: {
                          store: new Set([])
                        },
                        extensions: {
                          store: new Set([])
                        },
                        mainFields: {
                          store: new Set([])
                        },
                        mainFiles: {
                          store: new Set([])
                        },
                        modules: {
                          store: new Set([])
                        },
                        plugins: {
                          store: new Map([])
                        },
                        shorthands: [
                          'cachePredicate',
                          'cacheWithContext',
                          'concord',
                          'enforceExtension',
                          'enforceModuleExtension',
                          'symlinks',
                          'unsafeCache'
                        ],
                        cachePredicate: (value) => this.set(method, value),
                        cacheWithContext: (value) => this.set(method, value),
                        concord: (value) => this.set(method, value),
                        enforceExtension: (value) => this.set(method, value),
                        enforceModuleExtension: (value) => this.set(method, value),
                        symlinks: (value) => this.set(method, value),
                        unsafeCache: (value) => this.set(method, value)
                      },
                      shorthands: [
                        'enforce',
                        'issuer',
                        'parser',
                        'resource',
                        'resourceQuery',
                        'sideEffects',
                        'test',
                        'type'
                      ],
                      enforce: (value) => this.set(method, value),
                      issuer: (value) => this.set(method, value),
                      parser: (value) => this.set(method, value),
                      resource: (value) => this.set(method, value),
                      resourceQuery: (value) => this.set(method, value),
                      sideEffects: (value) => this.set(method, value),
                      test: (value) => this.set(method, value),
                      type: (value) => this.set(method, value)
                    }
                  ],
                  [
                    'media',
                    {
                      store: new Map([
                        [
                          'test',
                          /\.(mp4|webm|ogg|mp3|m4a|wav|flac|aac)(\?.*)?$/
                        ],
                        [
                          'type',
                          'asset'
                        ],
                        [
                          'parser',
                          {
                            dataUrlCondition: {
                              maxSize: 10240
                            }
                          }
                        ],
                        [
                          'generator',
                          {
                            emit: undefined,
                            outputPath: undefined,
                            publicPath: undefined,
                            filename: function () { /* omitted long function */ }
                          }
                        ]
                      ]),
                      name: 'media',
                      names: [
                        'media'
                      ],
                      ruleType: 'rule',
                      ruleTypes: [
                        'rule'
                      ],
                      uses: {
                        store: new Map([])
                      },
                      include: {
                        store: new Set([])
                      },
                      exclude: {
                        store: new Set([])
                      },
                      rules: {
                        store: new Map([])
                      },
                      oneOfs: {
                        store: new Map([])
                      },
                      resolve: {
                        store: new Map([]),
                        alias: {
                          store: new Map([])
                        },
                        aliasFields: {
                          store: new Set([])
                        },
                        descriptionFiles: {
                          store: new Set([])
                        },
                        extensions: {
                          store: new Set([])
                        },
                        mainFields: {
                          store: new Set([])
                        },
                        mainFiles: {
                          store: new Set([])
                        },
                        modules: {
                          store: new Set([])
                        },
                        plugins: {
                          store: new Map([])
                        },
                        shorthands: [
                          'cachePredicate',
                          'cacheWithContext',
                          'concord',
                          'enforceExtension',
                          'enforceModuleExtension',
                          'symlinks',
                          'unsafeCache'
                        ],
                        cachePredicate: (value) => this.set(method, value),
                        cacheWithContext: (value) => this.set(method, value),
                        concord: (value) => this.set(method, value),
                        enforceExtension: (value) => this.set(method, value),
                        enforceModuleExtension: (value) => this.set(method, value),
                        symlinks: (value) => this.set(method, value),
                        unsafeCache: (value) => this.set(method, value)
                      },
                      shorthands: [
                        'enforce',
                        'issuer',
                        'parser',
                        'resource',
                        'resourceQuery',
                        'sideEffects',
                        'test',
                        'type'
                      ],
                      enforce: (value) => this.set(method, value),
                      issuer: (value) => this.set(method, value),
                      parser: (value) => this.set(method, value),
                      resource: (value) => this.set(method, value),
                      resourceQuery: (value) => this.set(method, value),
                      sideEffects: (value) => this.set(method, value),
                      test: (value) => this.set(method, value),
                      type: (value) => this.set(method, value)
                    }
                  ],
                  [
                    'font',
                    {
                      store: new Map([
                        [
                          'test',
                          /\.(woff2?|eot|ttf|otf)(\?.*)?$/
                        ],
                        [
                          'type',
                          'asset'
                        ],
                        [
                          'parser',
                          {
                            dataUrlCondition: {
                              maxSize: 10240
                            }
                          }
                        ],
                        [
                          'generator',
                          {
                            emit: undefined,
                            outputPath: undefined,
                            publicPath: undefined,
                            filename: function () { /* omitted long function */ }
                          }
                        ]
                      ]),
                      name: 'font',
                      names: [
                        'font'
                      ],
                      ruleType: 'rule',
                      ruleTypes: [
                        'rule'
                      ],
                      uses: {
                        store: new Map([])
                      },
                      include: {
                        store: new Set([])
                      },
                      exclude: {
                        store: new Set([])
                      },
                      rules: {
                        store: new Map([])
                      },
                      oneOfs: {
                        store: new Map([])
                      },
                      resolve: {
                        store: new Map([]),
                        alias: {
                          store: new Map([])
                        },
                        aliasFields: {
                          store: new Set([])
                        },
                        descriptionFiles: {
                          store: new Set([])
                        },
                        extensions: {
                          store: new Set([])
                        },
                        mainFields: {
                          store: new Set([])
                        },
                        mainFiles: {
                          store: new Set([])
                        },
                        modules: {
                          store: new Set([])
                        },
                        plugins: {
                          store: new Map([])
                        },
                        shorthands: [
                          'cachePredicate',
                          'cacheWithContext',
                          'concord',
                          'enforceExtension',
                          'enforceModuleExtension',
                          'symlinks',
                          'unsafeCache'
                        ],
                        cachePredicate: (value) => this.set(method, value),
                        cacheWithContext: (value) => this.set(method, value),
                        concord: (value) => this.set(method, value),
                        enforceExtension: (value) => this.set(method, value),
                        enforceModuleExtension: (value) => this.set(method, value),
                        symlinks: (value) => this.set(method, value),
                        unsafeCache: (value) => this.set(method, value)
                      },
                      shorthands: [
                        'enforce',
                        'issuer',
                        'parser',
                        'resource',
                        'resourceQuery',
                        'sideEffects',
                        'test',
                        'type'
                      ],
                      enforce: (value) => this.set(method, value),
                      issuer: (value) => this.set(method, value),
                      parser: (value) => this.set(method, value),
                      resource: (value) => this.set(method, value),
                      resourceQuery: (value) => this.set(method, value),
                      sideEffects: (value) => this.set(method, value),
                      test: (value) => this.set(method, value),
                      type: (value) => this.set(method, value)
                    }
                  ],
                  [
                    'image',
                    {
                      store: new Map([
                        [
                          'test',
                          /\.(png|jpe?g|gif|bpm|svg|webp)(\?.*)?$/
                        ],
                        [
                          'type',
                          'asset'
                        ],
                        [
                          'parser',
                          {
                            dataUrlCondition: {
                              maxSize: 2048
                            }
                          }
                        ],
                        [
                          'generator',
                          {
                            emit: undefined,
                            outputPath: undefined,
                            publicPath: undefined,
                            filename: function () { /* omitted long function */ }
                          }
                        ]
                      ]),
                      name: 'image',
                      names: [
                        'image'
                      ],
                      ruleType: 'rule',
                      ruleTypes: [
                        'rule'
                      ],
                      uses: {
                        store: new Map([])
                      },
                      include: {
                        store: new Set([])
                      },
                      exclude: {
                        store: new Set([])
                      },
                      rules: {
                        store: new Map([])
                      },
                      oneOfs: {
                        store: new Map([])
                      },
                      resolve: {
                        store: new Map([]),
                        alias: {
                          store: new Map([])
                        },
                        aliasFields: {
                          store: new Set([])
                        },
                        descriptionFiles: {
                          store: new Set([])
                        },
                        extensions: {
                          store: new Set([])
                        },
                        mainFields: {
                          store: new Set([])
                        },
                        mainFiles: {
                          store: new Set([])
                        },
                        modules: {
                          store: new Set([])
                        },
                        plugins: {
                          store: new Map([])
                        },
                        shorthands: [
                          'cachePredicate',
                          'cacheWithContext',
                          'concord',
                          'enforceExtension',
                          'enforceModuleExtension',
                          'symlinks',
                          'unsafeCache'
                        ],
                        cachePredicate: (value) => this.set(method, value),
                        cacheWithContext: (value) => this.set(method, value),
                        concord: (value) => this.set(method, value),
                        enforceExtension: (value) => this.set(method, value),
                        enforceModuleExtension: (value) => this.set(method, value),
                        symlinks: (value) => this.set(method, value),
                        unsafeCache: (value) => this.set(method, value)
                      },
                      shorthands: [
                        'enforce',
                        'issuer',
                        'parser',
                        'resource',
                        'resourceQuery',
                        'sideEffects',
                        'test',
                        'type'
                      ],
                      enforce: (value) => this.set(method, value),
                      issuer: (value) => this.set(method, value),
                      parser: (value) => this.set(method, value),
                      resource: (value) => this.set(method, value),
                      resourceQuery: (value) => this.set(method, value),
                      sideEffects: (value) => this.set(method, value),
                      test: (value) => this.set(method, value),
                      type: (value) => this.set(method, value)
                    }
                  ],
                  [
                    'process-import-taro-h5',
                    {
                      store: new Map([
                        [
                          'test',
                          /taro-h5[\\/]dist[\\/](api[\\/]taro|index\.esm)/
                        ],
                        [
                          'loader',
                          'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\@tarojs\\plugin-framework-react\\dist\\api-loader.js'
                        ]
                      ]),
                      name: 'process-import-taro-h5',
                      names: [
                        'process-import-taro-h5'
                      ],
                      ruleType: 'rule',
                      ruleTypes: [
                        'rule'
                      ],
                      uses: {
                        store: new Map([])
                      },
                      include: {
                        store: new Set([])
                      },
                      exclude: {
                        store: new Set([])
                      },
                      rules: {
                        store: new Map([])
                      },
                      oneOfs: {
                        store: new Map([])
                      },
                      resolve: {
                        store: new Map([]),
                        alias: {
                          store: new Map([])
                        },
                        aliasFields: {
                          store: new Set([])
                        },
                        descriptionFiles: {
                          store: new Set([])
                        },
                        extensions: {
                          store: new Set([])
                        },
                        mainFields: {
                          store: new Set([])
                        },
                        mainFiles: {
                          store: new Set([])
                        },
                        modules: {
                          store: new Set([])
                        },
                        plugins: {
                          store: new Map([])
                        },
                        shorthands: [
                          'cachePredicate',
                          'cacheWithContext',
                          'concord',
                          'enforceExtension',
                          'enforceModuleExtension',
                          'symlinks',
                          'unsafeCache'
                        ],
                        cachePredicate: (value) => this.set(method, value),
                        cacheWithContext: (value) => this.set(method, value),
                        concord: (value) => this.set(method, value),
                        enforceExtension: (value) => this.set(method, value),
                        enforceModuleExtension: (value) => this.set(method, value),
                        symlinks: (value) => this.set(method, value),
                        unsafeCache: (value) => this.set(method, value)
                      },
                      shorthands: [
                        'enforce',
                        'issuer',
                        'parser',
                        'resource',
                        'resourceQuery',
                        'sideEffects',
                        'test',
                        'type'
                      ],
                      enforce: (value) => this.set(method, value),
                      issuer: (value) => this.set(method, value),
                      parser: (value) => this.set(method, value),
                      resource: (value) => this.set(method, value),
                      resourceQuery: (value) => this.set(method, value),
                      sideEffects: (value) => this.set(method, value),
                      test: (value) => this.set(method, value),
                      type: (value) => this.set(method, value)
                    }
                  ],
                  [
                    'map',
                    {
                      store: new Map([
                        [
                          'test',
                          /\.map$/
                        ],
                        [
                          'type',
                          'json'
                        ]
                      ]),
                      name: 'map',
                      names: [
                        'map'
                      ],
                      ruleType: 'rule',
                      ruleTypes: [
                        'rule'
                      ],
                      uses: {
                        store: new Map([])
                      },
                      include: {
                        store: new Set([])
                      },
                      exclude: {
                        store: new Set([])
                      },
                      rules: {
                        store: new Map([])
                      },
                      oneOfs: {
                        store: new Map([])
                      },
                      resolve: {
                        store: new Map([]),
                        alias: {
                          store: new Map([])
                        },
                        aliasFields: {
                          store: new Set([])
                        },
                        descriptionFiles: {
                          store: new Set([])
                        },
                        extensions: {
                          store: new Set([])
                        },
                        mainFields: {
                          store: new Set([])
                        },
                        mainFiles: {
                          store: new Set([])
                        },
                        modules: {
                          store: new Set([])
                        },
                        plugins: {
                          store: new Map([])
                        },
                        shorthands: [
                          'cachePredicate',
                          'cacheWithContext',
                          'concord',
                          'enforceExtension',
                          'enforceModuleExtension',
                          'symlinks',
                          'unsafeCache'
                        ],
                        cachePredicate: (value) => this.set(method, value),
                        cacheWithContext: (value) => this.set(method, value),
                        concord: (value) => this.set(method, value),
                        enforceExtension: (value) => this.set(method, value),
                        enforceModuleExtension: (value) => this.set(method, value),
                        symlinks: (value) => this.set(method, value),
                        unsafeCache: (value) => this.set(method, value)
                      },
                      shorthands: [
                        'enforce',
                        'issuer',
                        'parser',
                        'resource',
                        'resourceQuery',
                        'sideEffects',
                        'test',
                        'type'
                      ],
                      enforce: (value) => this.set(method, value),
                      issuer: (value) => this.set(method, value),
                      parser: (value) => this.set(method, value),
                      resource: (value) => this.set(method, value),
                      resourceQuery: (value) => this.set(method, value),
                      sideEffects: (value) => this.set(method, value),
                      test: (value) => this.set(method, value),
                      type: (value) => this.set(method, value)
                    }
                  ]
                ])
              },
              defaultRules: {
                store: new Map([])
              },
              shorthands: [
                'noParse',
                'strictExportPresence'
              ],
              noParse: (value) => this.set(method, value),
              strictExportPresence: (value) => this.set(method, value)
            },
            node: {
              store: new Map([])
            },
            optimization: {
              store: new Map([
                [
                  'minimize',
                  true
                ],
                [
                  'nodeEnv',
                  'production'
                ],
                [
                  'chunkIds',
                  'deterministic'
                ],
                [
                  'removeEmptyChunks',
                  true
                ],
                [
                  'splitChunks',
                  {
                    chunks: 'initial',
                    hidePathInfo: true,
                    minSize: 0,
                    cacheGroups: {
                      'default': false,
                      defaultVendors: false,
                      common: {
                        name: false,
                        minChunks: 2,
                        priority: 1
                      },
                      vendors: {
                        name: false,
                        minChunks: 2,
                        test: function () { /* omitted long function */ },
                        priority: 10
                      },
                      taro: {
                        name: false,
                        test: (module) => helper_1.REG_TARO_SCOPED_PACKAGE.test(module.context),
                        priority: 100
                      }
                    }
                  }
                ]
              ]),
              minimizers: {
                store: new Map([
                  [
                    'terserPlugin',
                    {
                      store: new Map([
                        [
                          'init',
                          function () { /* omitted long function */ }
                        ],
                        [
                          'plugin',
                          function () { /* omitted long function */ }
                        ],
                        [
                          'args',
                          [
                            {
                              parallel: true,
                              terserOptions: {
                                keep_fnames: true,
                                output: {
                                  comments: false,
                                  keep_quoted_props: true,
                                  quote_keys: true,
                                  beautify: false
                                },
                                warnings: false
                              }
                            }
                          ]
                        ]
                      ]),
                      name: 'terserPlugin',
                      type: 'optimization.minimizer',
                      shorthands: [
                        'init'
                      ],
                      init: (value) => this.set(method, value)
                    }
                  ],
                  [
                    'cssoWebpackPlugin',
                    {
                      store: new Map([
                        [
                          'init',
                          function () { /* omitted long function */ }
                        ],
                        [
                          'plugin',
                          function () { /* omitted long function */ }
                        ],
                        [
                          'args',
                          [
                            {
                              test: /\.(css|scss|sass|less|styl|stylus|wxss|acss|ttss|jxss|qss)(\?.*)?$/,
                              parallel: true,
                              minify: function () { /* omitted long function */ },
                              minimizerOptions: {
                                preset: [
                                  'default',
                                  {
                                    mergeRules: false,
                                    mergeIdents: false,
                                    reduceIdents: false,
                                    discardUnused: false,
                                    minifySelectors: false
                                  }
                                ]
                              }
                            }
                          ]
                        ]
                      ]),
                      name: 'cssoWebpackPlugin',
                      type: 'optimization.minimizer',
                      shorthands: [
                        'init'
                      ],
                      init: (value) => this.set(method, value)
                    }
                  ]
                ])
              },
              shorthands: [
                'concatenateModules',
                'flagIncludedChunks',
                'mergeDuplicateChunks',
                'minimize',
                'namedChunks',
                'namedModules',
                'nodeEnv',
                'noEmitOnErrors',
                'occurrenceOrder',
                'portableRecords',
                'providedExports',
                'removeAvailableModules',
                'removeEmptyChunks',
                'runtimeChunk',
                'sideEffects',
                'splitChunks',
                'usedExports'
              ],
              concatenateModules: (value) => this.set(method, value),
              flagIncludedChunks: (value) => this.set(method, value),
              mergeDuplicateChunks: (value) => this.set(method, value),
              minimize: (value) => this.set(method, value),
              namedChunks: (value) => this.set(method, value),
              namedModules: (value) => this.set(method, value),
              nodeEnv: (value) => this.set(method, value),
              noEmitOnErrors: (value) => this.set(method, value),
              occurrenceOrder: (value) => this.set(method, value),
              portableRecords: (value) => this.set(method, value),
              providedExports: (value) => this.set(method, value),
              removeAvailableModules: (value) => this.set(method, value),
              removeEmptyChunks: (value) => this.set(method, value),
              runtimeChunk: (value) => this.set(method, value),
              sideEffects: (value) => this.set(method, value),
              splitChunks: (value) => this.set(method, value),
              usedExports: (value) => this.set(method, value)
            },
            output: {
              store: new Map([
                [
                  'chunkLoadingGlobal',
                  'webpackJsonp'
                ],
                [
                  'path',
                  'C:\\Code\\FamilyClaw\\apps\\user-app\\dist'
                ],
                [
                  'filename',
                  'js/[name].[hash:8].js'
                ],
                [
                  'chunkFilename',
                  'js/[name].[chunkhash:8].js'
                ],
                [
                  'publicPath',
                  '/'
                ]
              ]),
              shorthands: [
                'auxiliaryComment',
                'chunkCallbackName',
                'chunkFilename',
                'chunkLoadTimeout',
                'crossOriginLoading',
                'devtoolFallbackModuleFilenameTemplate',
                'devtoolLineToLine',
                'devtoolModuleFilenameTemplate',
                'devtoolNamespace',
                'filename',
                'futureEmitAssets',
                'globalObject',
                'hashDigest',
                'hashDigestLength',
                'hashFunction',
                'hashSalt',
                'hotUpdateChunkFilename',
                'hotUpdateFunction',
                'hotUpdateMainFilename',
                'jsonpFunction',
                'library',
                'libraryExport',
                'libraryTarget',
                'path',
                'pathinfo',
                'publicPath',
                'sourceMapFilename',
                'sourcePrefix',
                'strictModuleExceptionHandling',
                'umdNamedDefine',
                'webassemblyModuleFilename'
              ],
              auxiliaryComment: (value) => this.set(method, value),
              chunkCallbackName: (value) => this.set(method, value),
              chunkFilename: (value) => this.set(method, value),
              chunkLoadTimeout: (value) => this.set(method, value),
              crossOriginLoading: (value) => this.set(method, value),
              devtoolFallbackModuleFilenameTemplate: (value) => this.set(method, value),
              devtoolLineToLine: (value) => this.set(method, value),
              devtoolModuleFilenameTemplate: (value) => this.set(method, value),
              devtoolNamespace: (value) => this.set(method, value),
              filename: (value) => this.set(method, value),
              futureEmitAssets: (value) => this.set(method, value),
              globalObject: (value) => this.set(method, value),
              hashDigest: (value) => this.set(method, value),
              hashDigestLength: (value) => this.set(method, value),
              hashFunction: (value) => this.set(method, value),
              hashSalt: (value) => this.set(method, value),
              hotUpdateChunkFilename: (value) => this.set(method, value),
              hotUpdateFunction: (value) => this.set(method, value),
              hotUpdateMainFilename: (value) => this.set(method, value),
              jsonpFunction: (value) => this.set(method, value),
              library: (value) => this.set(method, value),
              libraryExport: (value) => this.set(method, value),
              libraryTarget: (value) => this.set(method, value),
              path: (value) => this.set(method, value),
              pathinfo: (value) => this.set(method, value),
              publicPath: (value) => this.set(method, value),
              sourceMapFilename: (value) => this.set(method, value),
              sourcePrefix: (value) => this.set(method, value),
              strictModuleExceptionHandling: (value) => this.set(method, value),
              umdNamedDefine: (value) => this.set(method, value),
              webassemblyModuleFilename: (value) => this.set(method, value)
            },
            performance: {
              store: new Map([]),
              shorthands: [
                'assetFilter',
                'hints',
                'maxAssetSize',
                'maxEntrypointSize'
              ],
              assetFilter: (value) => this.set(method, value),
              hints: (value) => this.set(method, value),
              maxAssetSize: (value) => this.set(method, value),
              maxEntrypointSize: (value) => this.set(method, value)
            },
            plugins: {
              store: new Map([
                [
                  'webpackbar',
                  {
                    store: new Map([
                      [
                        'init',
                        function () { /* omitted long function */ }
                      ],
                      [
                        'plugin',
                        function () { /* omitted long function */ }
                      ],
                      [
                        'args',
                        [
                          {
                            reporters: [
                              'basic',
                              'fancy',
                              {
                                done: function () { /* omitted long function */ }
                              }
                            ],
                            basic: false,
                            fancy: true
                          }
                        ]
                      ]
                    ]),
                    name: 'webpackbar',
                    type: 'plugin',
                    shorthands: [
                      'init'
                    ],
                    init: (value) => this.set(method, value)
                  }
                ],
                [
                  'definePlugin',
                  {
                    store: new Map([
                      [
                        'init',
                        function () { /* omitted long function */ }
                      ],
                      [
                        'plugin',
                        function () { /* omitted long function */ }
                      ],
                      [
                        'args',
                        [
                          {
                            'process.env.FRAMEWORK': '"react"',
                            'process.env.TARO_ENV': '"h5"',
                            'process.env.TARO_PLATFORM': '"web"',
                            'process.env.TARO_VERSION': '"4.1.11"',
                            'process.env.SUPPORT_TARO_POLYFILL': '"disabled"',
                            'process.env.SUPPORT_DINGTALK_NAVIGATE': '"disabled"',
                            DEPRECATED_ADAPTER_COMPONENT: 'false'
                          }
                        ]
                      ]
                    ]),
                    name: 'definePlugin',
                    type: 'plugin',
                    shorthands: [
                      'init'
                    ],
                    init: (value) => this.set(method, value)
                  }
                ],
                [
                  'mainPlugin',
                  {
                    store: new Map([
                      [
                        'init',
                        function () { /* omitted long function */ }
                      ],
                      [
                        'plugin',
                        function () { /* omitted long function */ }
                      ],
                      [
                        'args',
                        [
                          {
                            appPath: 'C:\\Code\\FamilyClaw\\apps\\user-app',
                            sourceDir: 'C:\\Code\\FamilyClaw\\apps\\user-app\\src',
                            entryFileName: 'app',
                            framework: 'react',
                            frameworkExts: [
                              '.js',
                              '.jsx',
                              '.ts',
                              '.tsx'
                            ],
                            routerConfig: {
                              mode: 'browser'
                            },
                            runtimePath: '@tarojs/plugin-platform-h5/dist/runtime',
                            pxTransformConfig: {
                              platform: 'h5',
                              designWidth: 750
                            },
                            alias: {
                              '@': 'C:\\Code\\FamilyClaw\\apps\\user-app\\src'
                            },
                            defineConstants: {},
                            prebundle: false,
                            isBuildNativeComp: false,
                            noInjectGlobalStyle: false,
                            modifyAppConfig: undefined,
                            onCompilerMake: undefined,
                            onParseCreateElement: undefined,
                            loaderMeta: {
                              importFrameworkStatement: '\nimport * as React from \'react\'\nimport ReactDOM from \'react-dom/client\'\n',
                              mockAppStatement: '\nclass App extends React.Component {\n  render () {\n    return this.props.children\n  }\n}\n',
                              frameworkArgs: 'React, ReactDOM, config',
                              creator: 'createReactApp',
                              creatorLocation: '@tarojs/plugin-framework-react/dist/runtime',
                              importFrameworkName: 'React',
                              extraImportForWeb: 'import { findDOMNode, render, unstable_batchedUpdates } from \'react-dom\'\nimport { defineCustomElementTaroPullToRefreshCore } from \'@tarojs/components/dist/components\'\n',
                              execBeforeCreateWebApp: 'Object.assign(ReactDOM, { findDOMNode, render, unstable_batchedUpdates })\ndefineCustomElementTaroPullToRefreshCore()\n',
                              modifyConfig(config, source) {
                                  Object.assign(config, addConfig(source));
                              }
                            }
                          }
                        ]
                      ]
                    ]),
                    name: 'mainPlugin',
                    type: 'plugin',
                    shorthands: [
                      'init'
                    ],
                    init: (value) => this.set(method, value)
                  }
                ],
                [
                  'miniCssExtractPlugin',
                  {
                    store: new Map([
                      [
                        'init',
                        function () { /* omitted long function */ }
                      ],
                      [
                        'plugin',
                        function () { /* omitted long function */ }
                      ],
                      [
                        'args',
                        [
                          {
                            filename: 'css/[name].css',
                            chunkFilename: 'css/[name].css'
                          }
                        ]
                      ]
                    ]),
                    name: 'miniCssExtractPlugin',
                    type: 'plugin',
                    shorthands: [
                      'init'
                    ],
                    init: (value) => this.set(method, value)
                  }
                ]
              ])
            },
            resolve: {
              store: new Map([
                [
                  'symlinks',
                  true
                ]
              ]),
              alias: {
                store: new Map([
                  [
                    '@tarojs/runtime',
                    'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\@tarojs\\runtime\\dist\\index.js'
                  ],
                  [
                    '@tarojs/shared',
                    'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\@tarojs\\shared\\dist\\index.js'
                  ],
                  [
                    '@',
                    'C:\\Code\\FamilyClaw\\apps\\user-app\\src'
                  ],
                  [
                    'react$',
                    'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\react\\index.js'
                  ],
                  [
                    'react-dom$',
                    'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\react-dom\\index.js'
                  ],
                  [
                    '@tarojs/components$',
                    'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\@tarojs\\components\\lib\\react\\index.js'
                  ],
                  [
                    '@tarojs/components/lib',
                    'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\@tarojs\\components\\lib'
                  ],
                  [
                    '@tarojs/router$',
                    'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\@tarojs\\router\\dist\\index.js'
                  ],
                  [
                    '@tarojs/taro',
                    'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\@tarojs\\plugin-platform-h5\\dist\\runtime\\apis\\index.js'
                  ]
                ])
              },
              aliasFields: {
                store: new Set([])
              },
              descriptionFiles: {
                store: new Set([])
              },
              extensions: {
                store: new Set([
                  '.js',
                  '.jsx',
                  '.ts',
                  '.tsx',
                  '.mjs',
                  '.vue'
                ])
              },
              mainFields: {
                store: new Set([
                  'browser',
                  'module',
                  'jsnext:main',
                  'main'
                ])
              },
              mainFiles: {
                store: new Set([])
              },
              modules: {
                store: new Set([])
              },
              plugins: {
                store: new Map([
                  [
                    'MultiPlatformPlugin',
                    {
                      store: new Map([
                        [
                          'init',
                          function () { /* omitted long function */ }
                        ],
                        [
                          'plugin',
                          function () { /* omitted long function */ }
                        ],
                        [
                          'args',
                          [
                            'described-resolve',
                            'resolve',
                          undefined
                          ]
                        ]
                      ]),
                      name: 'MultiPlatformPlugin',
                      type: 'resolve.plugin',
                      shorthands: [
                        'init'
                      ],
                      init: (value) => this.set(method, value)
                    }
                  ]
                ])
              },
              shorthands: [
                'cachePredicate',
                'cacheWithContext',
                'concord',
                'enforceExtension',
                'enforceModuleExtension',
                'symlinks',
                'unsafeCache'
              ],
              cachePredicate: (value) => this.set(method, value),
              cacheWithContext: (value) => this.set(method, value),
              concord: (value) => this.set(method, value),
              enforceExtension: (value) => this.set(method, value),
              enforceModuleExtension: (value) => this.set(method, value),
              symlinks: (value) => this.set(method, value),
              unsafeCache: (value) => this.set(method, value)
            },
            resolveLoader: {
              store: new Map([]),
              alias: {
                store: new Map([])
              },
              aliasFields: {
                store: new Set([])
              },
              descriptionFiles: {
                store: new Set([])
              },
              extensions: {
                store: new Set([])
              },
              mainFields: {
                store: new Set([])
              },
              mainFiles: {
                store: new Set([])
              },
              modules: {
                store: new Set([
                  'node_modules'
                ])
              },
              plugins: {
                store: new Map([])
              },
              shorthands: [
                'cachePredicate',
                'cacheWithContext',
                'concord',
                'enforceExtension',
                'enforceModuleExtension',
                'symlinks',
                'unsafeCache'
              ],
              cachePredicate: (value) => this.set(method, value),
              cacheWithContext: (value) => this.set(method, value),
              concord: (value) => this.set(method, value),
              enforceExtension: (value) => this.set(method, value),
              enforceModuleExtension: (value) => this.set(method, value),
              symlinks: (value) => this.set(method, value),
              unsafeCache: (value) => this.set(method, value),
              moduleExtensions: {
                store: new Set([])
              },
              packageMains: {
                store: new Set([])
              }
            },
            shorthands: [
              'amd',
              'bail',
              'cache',
              'context',
              'devtool',
              'externals',
              'loader',
              'mode',
              'name',
              'parallelism',
              'profile',
              'recordsInputPath',
              'recordsPath',
              'recordsOutputPath',
              'stats',
              'target',
              'watch',
              'watchOptions'
            ],
            amd: (value) => this.set(method, value),
            bail: (value) => this.set(method, value),
            cache: (value) => this.set(method, value),
            context: (value) => this.set(method, value),
            devtool: (value) => this.set(method, value),
            externals: (value) => this.set(method, value),
            loader: (value) => this.set(method, value),
            mode: (value) => this.set(method, value),
            name: (value) => this.set(method, value),
            parallelism: (value) => this.set(method, value),
            profile: (value) => this.set(method, value),
            recordsInputPath: (value) => this.set(method, value),
            recordsPath: (value) => this.set(method, value),
            recordsOutputPath: (value) => this.set(method, value),
            stats: (value) => this.set(method, value),
            target: (value) => this.set(method, value),
            watch: (value) => this.set(method, value),
            watchOptions: (value) => this.set(method, value)
          }
        }
      )
    ]
  },
  resolveLoader: {
    modules: [
      'node_modules'
    ]
  },
  module: {
    rules: [
      /* config.module.rule('taroStyle') */
      {
        test: /\.(css|scss|sass|less|styl|stylus|wxss|acss|ttss|jxss|qss)(\?.*)?$/,
        include: [
          (filename) => isTaroModule(filename)
        ],
        use: [
          /* config.module.rule('taroStyle').use('0') */
          {
            loader: 'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\style-loader\\dist\\cjs.js',
            options: {
              insert: function () { /* omitted long function */ }
            }
          }
        ]
      },
      /* config.module.rule('customStyle') */
      {
        test: /\.(css|scss|sass|less|styl|stylus|wxss|acss|ttss|jxss|qss)(\?.*)?$/,
        exclude: [
          (filename) => isTaroModule(filename)
        ],
        use: [
          /* config.module.rule('customStyle').use('0') */
          {
            loader: 'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\mini-css-extract-plugin\\dist\\loader.js'
          }
        ]
      },
      /* config.module.rule('css') */
      {
        test: /\.(css|scss|sass|less|styl|stylus|wxss|acss|ttss|jxss|qss)(\?.*)?$/,
        oneOf: [
          /* config.module.rule('css').oneOf('0') */
          {
            use: [
              /* config.module.rule('css').oneOf('0').use('0') */
              {
                loader: 'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\css-loader\\dist\\cjs.js',
                options: {
                  importLoaders: 1,
                  modules: false
                }
              }
            ]
          }
        ]
      },
      /* config.module.rule('postcss') */
      {
        test: /\.(css|scss|sass|less|styl|stylus|wxss|acss|ttss|jxss|qss)(\?.*)?$/,
        exclude: [
          function () { /* omitted long function */ }
        ],
        use: [
          /* config.module.rule('postcss').use('0') */
          {
            loader: 'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\postcss-loader\\dist\\cjs.js',
            options: {
              postcssOptions: {
                plugins: [
                  {
                    postcssPlugin: 'postcss-import',
                    Once: function () { /* omitted long function */ }
                  },
                  {
                    browsers: undefined,
                    info: function () { /* omitted long function */ },
                    options: {
                      flexbox: 'no-2009'
                    },
                    postcssPlugin: 'autoprefixer',
                    prepare: function () { /* omitted long function */ }
                  },
                  {
                    postcssPlugin: 'postcss-pxtransform',
                    prepare: function () { /* omitted long function */ }
                  },
                  {
                    postcssPlugin: 'postcss-html-transform',
                    Rule: function () { /* omitted long function */ },
                    Declaration: function () { /* omitted long function */ }
                  },
                  {
                    postcssPlugin: 'postcss-plugin-constparse',
                    Declaration: function () { /* omitted long function */ }
                  },
                  {
                    postcssPlugin: 'postcss-alias',
                    Once: function () { /* omitted long function */ }
                  },
                  {
                    postcssPlugin: 'postcss-url',
                    Once: function () { /* omitted long function */ }
                  }
                ]
              }
            }
          }
        ]
      },
      /* config.module.rule('sass') */
      {
        test: /\.sass$/,
        use: [
          /* config.module.rule('sass').use('0') */
          {
            loader: 'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\resolve-url-loader\\index.js'
          },
          /* config.module.rule('sass').use('1') */
          {
            loader: 'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\sass-loader\\dist\\cjs.js',
            options: {
              sourceMap: true,
              implementation: {
                load: function () { /* omitted long function */ },
                compile: function () {
                  return _call(f, Array.prototype.slice.apply(arguments));
                },
                compileString: function () {
                  return _call(f, Array.prototype.slice.apply(arguments));
                },
                compileAsync: function () {
                  return _call(f, Array.prototype.slice.apply(arguments));
                },
                compileStringAsync: function () {
                  return _call(f, Array.prototype.slice.apply(arguments));
                },
                initCompiler: function () {
                  return _call(f, Array.prototype.slice.apply(arguments));
                },
                initAsyncCompiler: function () {
                  return _call(f, Array.prototype.slice.apply(arguments));
                },
                Compiler: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                AsyncCompiler: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                Value: function Value0() {
                },
                SassBoolean: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                SassArgumentList: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                SassCalculation: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                CalculationOperation: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                CalculationInterpolation: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                SassColor: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                SassFunction: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                SassMixin: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                SassList: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                SassMap: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                SassNumber: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                SassString: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                sassNull: {},
                sassTrue: {
                  value: true
                },
                sassFalse: {
                  value: false
                },
                Exception: function () { /* omitted long function */ },
                Logger: {
                  silent: {
                    warn: function () {
                      return _call(f, Array.prototype.slice.apply(arguments));
                    },
                    debug: function () {
                      return _call(f, Array.prototype.slice.apply(arguments));
                    }
                  }
                },
                NodePackageImporter: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                deprecations: {
                  'call-string': {
                    id: 'call-string',
                    status: 'active',
                    description: 'Passing a string directly to meta.call().',
                    deprecatedIn: {
                      major: 0,
                      minor: 0,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '0.0.0'
                    },
                    obsoleteIn: null
                  },
                  elseif: {
                    id: 'elseif',
                    status: 'active',
                    description: '@elseif.',
                    deprecatedIn: {
                      major: 1,
                      minor: 3,
                      patch: 2,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.3.2'
                    },
                    obsoleteIn: null
                  },
                  'moz-document': {
                    id: 'moz-document',
                    status: 'active',
                    description: '@-moz-document.',
                    deprecatedIn: {
                      major: 1,
                      minor: 7,
                      patch: 2,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.7.2'
                    },
                    obsoleteIn: null
                  },
                  'relative-canonical': {
                    id: 'relative-canonical',
                    status: 'active',
                    description: 'Imports using relative canonical URLs.',
                    deprecatedIn: {
                      major: 1,
                      minor: 14,
                      patch: 2,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.14.2'
                    },
                    obsoleteIn: null
                  },
                  'new-global': {
                    id: 'new-global',
                    status: 'active',
                    description: 'Declaring new variables with !global.',
                    deprecatedIn: {
                      major: 1,
                      minor: 17,
                      patch: 2,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.17.2'
                    },
                    obsoleteIn: null
                  },
                  'color-module-compat': {
                    id: 'color-module-compat',
                    status: 'active',
                    description: 'Using color module functions in place of plain CSS functions.',
                    deprecatedIn: {
                      major: 1,
                      minor: 23,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.23.0'
                    },
                    obsoleteIn: null
                  },
                  'slash-div': {
                    id: 'slash-div',
                    status: 'active',
                    description: '/ operator for division.',
                    deprecatedIn: {
                      major: 1,
                      minor: 33,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.33.0'
                    },
                    obsoleteIn: null
                  },
                  'bogus-combinators': {
                    id: 'bogus-combinators',
                    status: 'active',
                    description: 'Leading, trailing, and repeated combinators.',
                    deprecatedIn: {
                      major: 1,
                      minor: 54,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.54.0'
                    },
                    obsoleteIn: null
                  },
                  'strict-unary': {
                    id: 'strict-unary',
                    status: 'active',
                    description: 'Ambiguous + and - operators.',
                    deprecatedIn: {
                      major: 1,
                      minor: 55,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.55.0'
                    },
                    obsoleteIn: null
                  },
                  'function-units': {
                    id: 'function-units',
                    status: 'active',
                    description: 'Passing invalid units to built-in functions.',
                    deprecatedIn: {
                      major: 1,
                      minor: 56,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.56.0'
                    },
                    obsoleteIn: null
                  },
                  'duplicate-var-flags': {
                    id: 'duplicate-var-flags',
                    status: 'active',
                    description: 'Using !default or !global multiple times for one variable.',
                    deprecatedIn: {
                      major: 1,
                      minor: 62,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.62.0'
                    },
                    obsoleteIn: null
                  },
                  'null-alpha': {
                    id: 'null-alpha',
                    status: 'active',
                    description: 'Passing null as alpha in the JS API.',
                    deprecatedIn: {
                      major: 1,
                      minor: 62,
                      patch: 3,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.62.3'
                    },
                    obsoleteIn: null
                  },
                  'abs-percent': {
                    id: 'abs-percent',
                    status: 'active',
                    description: 'Passing percentages to the Sass abs() function.',
                    deprecatedIn: {
                      major: 1,
                      minor: 65,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.65.0'
                    },
                    obsoleteIn: null
                  },
                  'fs-importer-cwd': {
                    id: 'fs-importer-cwd',
                    status: 'active',
                    description: 'Using the current working directory as an implicit load path.',
                    deprecatedIn: {
                      major: 1,
                      minor: 73,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.73.0'
                    },
                    obsoleteIn: null
                  },
                  'css-function-mixin': {
                    id: 'css-function-mixin',
                    status: 'obsolete',
                    description: 'Function and mixin names beginning with --.',
                    deprecatedIn: {
                      major: 1,
                      minor: 76,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.76.0'
                    },
                    obsoleteIn: {
                      major: 1,
                      minor: 94,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.94.0'
                    }
                  },
                  'mixed-decls': {
                    id: 'mixed-decls',
                    status: 'obsolete',
                    description: 'Declarations after or between nested rules.',
                    deprecatedIn: {
                      major: 1,
                      minor: 77,
                      patch: 7,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.77.7'
                    },
                    obsoleteIn: {
                      major: 1,
                      minor: 92,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.92.0'
                    }
                  },
                  'feature-exists': {
                    id: 'feature-exists',
                    status: 'active',
                    description: 'meta.feature-exists',
                    deprecatedIn: {
                      major: 1,
                      minor: 78,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.78.0'
                    },
                    obsoleteIn: null
                  },
                  'color-4-api': {
                    id: 'color-4-api',
                    status: 'active',
                    description: 'Certain uses of built-in sass:color functions.',
                    deprecatedIn: {
                      major: 1,
                      minor: 79,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.79.0'
                    },
                    obsoleteIn: null
                  },
                  'color-functions': {
                    id: 'color-functions',
                    status: 'active',
                    description: 'Using global color functions instead of sass:color.',
                    deprecatedIn: {
                      major: 1,
                      minor: 79,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.79.0'
                    },
                    obsoleteIn: null
                  },
                  'legacy-js-api': {
                    id: 'legacy-js-api',
                    status: 'active',
                    description: 'Legacy JS API.',
                    deprecatedIn: {
                      major: 1,
                      minor: 79,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.79.0'
                    },
                    obsoleteIn: null
                  },
                  'import': {
                    id: 'import',
                    status: 'active',
                    description: '@import rules.',
                    deprecatedIn: {
                      major: 1,
                      minor: 80,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.80.0'
                    },
                    obsoleteIn: null
                  },
                  'global-builtin': {
                    id: 'global-builtin',
                    status: 'active',
                    description: 'Global built-in functions that are available in sass: modules.',
                    deprecatedIn: {
                      major: 1,
                      minor: 80,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.80.0'
                    },
                    obsoleteIn: null
                  },
                  'type-function': {
                    id: 'type-function',
                    status: 'obsolete',
                    description: 'Functions named "type".',
                    deprecatedIn: {
                      major: 1,
                      minor: 86,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.86.0'
                    },
                    obsoleteIn: {
                      major: 1,
                      minor: 92,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.92.0'
                    }
                  },
                  'compile-string-relative-url': {
                    id: 'compile-string-relative-url',
                    status: 'active',
                    description: 'Passing a relative url to compileString().',
                    deprecatedIn: {
                      major: 1,
                      minor: 88,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.88.0'
                    },
                    obsoleteIn: null
                  },
                  'misplaced-rest': {
                    id: 'misplaced-rest',
                    status: 'active',
                    description: 'A rest parameter before a positional or named parameter.',
                    deprecatedIn: {
                      major: 1,
                      minor: 91,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.91.0'
                    },
                    obsoleteIn: null
                  },
                  'with-private': {
                    id: 'with-private',
                    status: 'active',
                    description: 'Configuring private variables in @use, @forward, or load-css().',
                    deprecatedIn: {
                      major: 1,
                      minor: 92,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.92.0'
                    },
                    obsoleteIn: null
                  },
                  'if-function': {
                    id: 'if-function',
                    status: 'active',
                    description: 'The Sass if($condition, $if-true, $if-false) function.',
                    deprecatedIn: {
                      major: 1,
                      minor: 95,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.95.0'
                    },
                    obsoleteIn: null
                  },
                  'user-authored': {
                    id: 'user-authored',
                    status: 'user',
                    description: null,
                    deprecatedIn: null,
                    obsoleteIn: null
                  }
                },
                Version: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                loadParserExports_: function () {
                  return _call(f, Array.prototype.slice.apply(arguments));
                },
                info: 'dart-sass\t1.98.0\t(Sass Compiler)\t[Dart]\ndart2js\t3.11.2\t(Dart Compiler)\t[Dart]',
                render: function () {
                  return _call(f, Array.prototype.slice.apply(arguments));
                },
                renderSync: function () {
                  return _call(f, Array.prototype.slice.apply(arguments));
                },
                types: {
                  Boolean: function () {
                    return _call(f, this, Array.prototype.slice.apply(arguments));
                  },
                  Color: function () {
                    return _call(f, this, Array.prototype.slice.apply(arguments));
                  },
                  List: function () {
                    return _call(f, this, Array.prototype.slice.apply(arguments));
                  },
                  Map: function () {
                    return _call(f, this, Array.prototype.slice.apply(arguments));
                  },
                  Null: function () {
                    return _call(f, this, Array.prototype.slice.apply(arguments));
                  },
                  Number: function () {
                    return _call(f, this, Array.prototype.slice.apply(arguments));
                  },
                  String: function () {
                    return _call(f, this, Array.prototype.slice.apply(arguments));
                  },
                  Error: function Error() { [native code] }
                },
                NULL: {},
                TRUE: {
                  value: true
                },
                FALSE: {
                  value: false
                },
                cli_pkg_main_0_: function () {
                  return _call(f, Array.prototype.slice.apply(arguments));
                }
              },
              sassOptions: {
                outputStyle: 'expanded',
                silenceDeprecations: [
                  'legacy-js-api'
                ],
                importer: function () { /* omitted long function */ },
                indentedSyntax: true
              }
            }
          }
        ]
      },
      /* config.module.rule('scss') */
      {
        test: /\.scss$/,
        use: [
          /* config.module.rule('scss').use('0') */
          {
            loader: 'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\resolve-url-loader\\index.js'
          },
          /* config.module.rule('scss').use('1') */
          {
            loader: 'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\sass-loader\\dist\\cjs.js',
            options: {
              sourceMap: true,
              implementation: {
                load: function () { /* omitted long function */ },
                compile: function () {
                  return _call(f, Array.prototype.slice.apply(arguments));
                },
                compileString: function () {
                  return _call(f, Array.prototype.slice.apply(arguments));
                },
                compileAsync: function () {
                  return _call(f, Array.prototype.slice.apply(arguments));
                },
                compileStringAsync: function () {
                  return _call(f, Array.prototype.slice.apply(arguments));
                },
                initCompiler: function () {
                  return _call(f, Array.prototype.slice.apply(arguments));
                },
                initAsyncCompiler: function () {
                  return _call(f, Array.prototype.slice.apply(arguments));
                },
                Compiler: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                AsyncCompiler: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                Value: function Value0() {
                },
                SassBoolean: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                SassArgumentList: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                SassCalculation: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                CalculationOperation: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                CalculationInterpolation: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                SassColor: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                SassFunction: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                SassMixin: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                SassList: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                SassMap: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                SassNumber: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                SassString: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                sassNull: {},
                sassTrue: {
                  value: true
                },
                sassFalse: {
                  value: false
                },
                Exception: function () { /* omitted long function */ },
                Logger: {
                  silent: {
                    warn: function () {
                      return _call(f, Array.prototype.slice.apply(arguments));
                    },
                    debug: function () {
                      return _call(f, Array.prototype.slice.apply(arguments));
                    }
                  }
                },
                NodePackageImporter: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                deprecations: {
                  'call-string': {
                    id: 'call-string',
                    status: 'active',
                    description: 'Passing a string directly to meta.call().',
                    deprecatedIn: {
                      major: 0,
                      minor: 0,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '0.0.0'
                    },
                    obsoleteIn: null
                  },
                  elseif: {
                    id: 'elseif',
                    status: 'active',
                    description: '@elseif.',
                    deprecatedIn: {
                      major: 1,
                      minor: 3,
                      patch: 2,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.3.2'
                    },
                    obsoleteIn: null
                  },
                  'moz-document': {
                    id: 'moz-document',
                    status: 'active',
                    description: '@-moz-document.',
                    deprecatedIn: {
                      major: 1,
                      minor: 7,
                      patch: 2,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.7.2'
                    },
                    obsoleteIn: null
                  },
                  'relative-canonical': {
                    id: 'relative-canonical',
                    status: 'active',
                    description: 'Imports using relative canonical URLs.',
                    deprecatedIn: {
                      major: 1,
                      minor: 14,
                      patch: 2,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.14.2'
                    },
                    obsoleteIn: null
                  },
                  'new-global': {
                    id: 'new-global',
                    status: 'active',
                    description: 'Declaring new variables with !global.',
                    deprecatedIn: {
                      major: 1,
                      minor: 17,
                      patch: 2,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.17.2'
                    },
                    obsoleteIn: null
                  },
                  'color-module-compat': {
                    id: 'color-module-compat',
                    status: 'active',
                    description: 'Using color module functions in place of plain CSS functions.',
                    deprecatedIn: {
                      major: 1,
                      minor: 23,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.23.0'
                    },
                    obsoleteIn: null
                  },
                  'slash-div': {
                    id: 'slash-div',
                    status: 'active',
                    description: '/ operator for division.',
                    deprecatedIn: {
                      major: 1,
                      minor: 33,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.33.0'
                    },
                    obsoleteIn: null
                  },
                  'bogus-combinators': {
                    id: 'bogus-combinators',
                    status: 'active',
                    description: 'Leading, trailing, and repeated combinators.',
                    deprecatedIn: {
                      major: 1,
                      minor: 54,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.54.0'
                    },
                    obsoleteIn: null
                  },
                  'strict-unary': {
                    id: 'strict-unary',
                    status: 'active',
                    description: 'Ambiguous + and - operators.',
                    deprecatedIn: {
                      major: 1,
                      minor: 55,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.55.0'
                    },
                    obsoleteIn: null
                  },
                  'function-units': {
                    id: 'function-units',
                    status: 'active',
                    description: 'Passing invalid units to built-in functions.',
                    deprecatedIn: {
                      major: 1,
                      minor: 56,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.56.0'
                    },
                    obsoleteIn: null
                  },
                  'duplicate-var-flags': {
                    id: 'duplicate-var-flags',
                    status: 'active',
                    description: 'Using !default or !global multiple times for one variable.',
                    deprecatedIn: {
                      major: 1,
                      minor: 62,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.62.0'
                    },
                    obsoleteIn: null
                  },
                  'null-alpha': {
                    id: 'null-alpha',
                    status: 'active',
                    description: 'Passing null as alpha in the JS API.',
                    deprecatedIn: {
                      major: 1,
                      minor: 62,
                      patch: 3,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.62.3'
                    },
                    obsoleteIn: null
                  },
                  'abs-percent': {
                    id: 'abs-percent',
                    status: 'active',
                    description: 'Passing percentages to the Sass abs() function.',
                    deprecatedIn: {
                      major: 1,
                      minor: 65,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.65.0'
                    },
                    obsoleteIn: null
                  },
                  'fs-importer-cwd': {
                    id: 'fs-importer-cwd',
                    status: 'active',
                    description: 'Using the current working directory as an implicit load path.',
                    deprecatedIn: {
                      major: 1,
                      minor: 73,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.73.0'
                    },
                    obsoleteIn: null
                  },
                  'css-function-mixin': {
                    id: 'css-function-mixin',
                    status: 'obsolete',
                    description: 'Function and mixin names beginning with --.',
                    deprecatedIn: {
                      major: 1,
                      minor: 76,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.76.0'
                    },
                    obsoleteIn: {
                      major: 1,
                      minor: 94,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.94.0'
                    }
                  },
                  'mixed-decls': {
                    id: 'mixed-decls',
                    status: 'obsolete',
                    description: 'Declarations after or between nested rules.',
                    deprecatedIn: {
                      major: 1,
                      minor: 77,
                      patch: 7,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.77.7'
                    },
                    obsoleteIn: {
                      major: 1,
                      minor: 92,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.92.0'
                    }
                  },
                  'feature-exists': {
                    id: 'feature-exists',
                    status: 'active',
                    description: 'meta.feature-exists',
                    deprecatedIn: {
                      major: 1,
                      minor: 78,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.78.0'
                    },
                    obsoleteIn: null
                  },
                  'color-4-api': {
                    id: 'color-4-api',
                    status: 'active',
                    description: 'Certain uses of built-in sass:color functions.',
                    deprecatedIn: {
                      major: 1,
                      minor: 79,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.79.0'
                    },
                    obsoleteIn: null
                  },
                  'color-functions': {
                    id: 'color-functions',
                    status: 'active',
                    description: 'Using global color functions instead of sass:color.',
                    deprecatedIn: {
                      major: 1,
                      minor: 79,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.79.0'
                    },
                    obsoleteIn: null
                  },
                  'legacy-js-api': {
                    id: 'legacy-js-api',
                    status: 'active',
                    description: 'Legacy JS API.',
                    deprecatedIn: {
                      major: 1,
                      minor: 79,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.79.0'
                    },
                    obsoleteIn: null
                  },
                  'import': {
                    id: 'import',
                    status: 'active',
                    description: '@import rules.',
                    deprecatedIn: {
                      major: 1,
                      minor: 80,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.80.0'
                    },
                    obsoleteIn: null
                  },
                  'global-builtin': {
                    id: 'global-builtin',
                    status: 'active',
                    description: 'Global built-in functions that are available in sass: modules.',
                    deprecatedIn: {
                      major: 1,
                      minor: 80,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.80.0'
                    },
                    obsoleteIn: null
                  },
                  'type-function': {
                    id: 'type-function',
                    status: 'obsolete',
                    description: 'Functions named "type".',
                    deprecatedIn: {
                      major: 1,
                      minor: 86,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.86.0'
                    },
                    obsoleteIn: {
                      major: 1,
                      minor: 92,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.92.0'
                    }
                  },
                  'compile-string-relative-url': {
                    id: 'compile-string-relative-url',
                    status: 'active',
                    description: 'Passing a relative url to compileString().',
                    deprecatedIn: {
                      major: 1,
                      minor: 88,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.88.0'
                    },
                    obsoleteIn: null
                  },
                  'misplaced-rest': {
                    id: 'misplaced-rest',
                    status: 'active',
                    description: 'A rest parameter before a positional or named parameter.',
                    deprecatedIn: {
                      major: 1,
                      minor: 91,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.91.0'
                    },
                    obsoleteIn: null
                  },
                  'with-private': {
                    id: 'with-private',
                    status: 'active',
                    description: 'Configuring private variables in @use, @forward, or load-css().',
                    deprecatedIn: {
                      major: 1,
                      minor: 92,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.92.0'
                    },
                    obsoleteIn: null
                  },
                  'if-function': {
                    id: 'if-function',
                    status: 'active',
                    description: 'The Sass if($condition, $if-true, $if-false) function.',
                    deprecatedIn: {
                      major: 1,
                      minor: 95,
                      patch: 0,
                      preRelease: [],
                      build: [],
                      _version$_text: '1.95.0'
                    },
                    obsoleteIn: null
                  },
                  'user-authored': {
                    id: 'user-authored',
                    status: 'user',
                    description: null,
                    deprecatedIn: null,
                    obsoleteIn: null
                  }
                },
                Version: function () {
                  return _call(f, this, Array.prototype.slice.apply(arguments));
                },
                loadParserExports_: function () {
                  return _call(f, Array.prototype.slice.apply(arguments));
                },
                info: 'dart-sass\t1.98.0\t(Sass Compiler)\t[Dart]\ndart2js\t3.11.2\t(Dart Compiler)\t[Dart]',
                render: function () {
                  return _call(f, Array.prototype.slice.apply(arguments));
                },
                renderSync: function () {
                  return _call(f, Array.prototype.slice.apply(arguments));
                },
                types: {
                  Boolean: function () {
                    return _call(f, this, Array.prototype.slice.apply(arguments));
                  },
                  Color: function () {
                    return _call(f, this, Array.prototype.slice.apply(arguments));
                  },
                  List: function () {
                    return _call(f, this, Array.prototype.slice.apply(arguments));
                  },
                  Map: function () {
                    return _call(f, this, Array.prototype.slice.apply(arguments));
                  },
                  Null: function () {
                    return _call(f, this, Array.prototype.slice.apply(arguments));
                  },
                  Number: function () {
                    return _call(f, this, Array.prototype.slice.apply(arguments));
                  },
                  String: function () {
                    return _call(f, this, Array.prototype.slice.apply(arguments));
                  },
                  Error: function Error() { [native code] }
                },
                NULL: {},
                TRUE: {
                  value: true
                },
                FALSE: {
                  value: false
                },
                cli_pkg_main_0_: function () {
                  return _call(f, Array.prototype.slice.apply(arguments));
                }
              },
              sassOptions: {
                outputStyle: 'expanded',
                silenceDeprecations: [
                  'legacy-js-api'
                ],
                importer: function () { /* omitted long function */ }
              }
            }
          }
        ]
      },
      /* config.module.rule('less') */
      {
        test: /\.less$/,
        use: [
          /* config.module.rule('less').use('0') */
          {
            loader: 'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\less-loader\\dist\\cjs.js'
          }
        ]
      },
      /* config.module.rule('stylus') */
      {
        test: /\.styl(us)?$/,
        use: [
          /* config.module.rule('stylus').use('0') */
          {
            loader: 'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\stylus-loader\\dist\\cjs.js'
          }
        ]
      },
      /* config.module.rule('script') */
      {
        test: /\.m?[tj]sx?$/i,
        include: [
          'C:\\Code\\FamilyClaw\\apps\\user-app\\src',
          filename => /(?<=node_modules[\\/]).*taro/.test(filename)
        ],
        use: [
          /* config.module.rule('script').use('babelLoader') */
          {
            loader: 'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\babel-loader\\lib\\index.js',
            options: {
              compact: false,
              plugins: [
                [
                  {
                    'default': function () { /* omitted long function */ }
                  },
                  {
                    packageName: '@tarojs/taro',
                    definition: {
                      apis: {
                        Behavior: '*',
                        getEnv: '*',
                        ENV_TYPE: '*',
                        Link: '*',
                        interceptors: '*',
                        interceptorify: '*',
                        Current: '*',
                        options: '*',
                        eventCenter: '*',
                        Events: '*',
                        preload: '*',
                        taro: {},
                        requirePlugin: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        initPxTransform: {
                          object: '{ designWidth?: number; deviceRatio?: TDeviceRatio; baseFontSize?: number; unitPrecision?: number; targetUnit?: string; }',
                          success: 'void'
                        },
                        pxTransform: {
                          object: 'number',
                          success: 'void',
                          'return': '*'
                        },
                        canIUseWebp: {
                          object: 'void',
                          success: 'void',
                          'return': 'boolean'
                        },
                        getAppInfo: {
                          object: 'void',
                          success: 'void',
                          'return': '{ platform: string; taroVersion: string; designWidth: any; }'
                        },
                        createRewardedVideoAd: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        createInterstitialAd: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        stopFaceDetect: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        initFaceDetect: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        faceDetect: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getInferenceEnvInfo: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        createInferenceSession: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        isVKSupport: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        createVKSession: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getOpenUserInfo: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        tradePay: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getUserCryptoManager: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        setEnableDebug: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getRealtimeLogManager: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getLogManager: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        reportPerformance: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getPerformance: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        preloadWebview: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        preloadSkylineView: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        preloadAssets: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        openSystemBluetoothSetting: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        openAppAuthorizeSetting: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getWindowInfo: {
                          object: 'void',
                          success: 'void',
                          'return': 'Result'
                        },
                        getSystemSetting: {
                          object: 'void',
                          success: 'void',
                          'return': 'Result'
                        },
                        getDeviceInfo: {
                          object: 'void',
                          success: 'void',
                          'return': 'Result'
                        },
                        getAppBaseInfo: {
                          object: 'void',
                          success: 'void',
                          'return': 'Result'
                        },
                        getAppAuthorizeSetting: {
                          object: 'void',
                          success: 'void',
                          'return': 'Result'
                        },
                        getSystemInfoSync: {
                          object: 'void',
                          success: 'void',
                          'return': 'Result'
                        },
                        getSystemInfoAsync: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<Result>'
                        },
                        getSystemInfo: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<Result>'
                        },
                        getSkylineInfoSync: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getSkylineInfo: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getRendererUserAgent: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        updateWeChatApp: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getUpdateManager: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onUnhandledRejection: {
                          callback: 'Result<T>'
                        },
                        onThemeChange: {
                          callback: 'Result'
                        },
                        onPageNotFound: {
                          callback: 'Result'
                        },
                        onLazyLoadError: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onError: {
                          callback: 'string | ErrorEvent | Error'
                        },
                        onAudioInterruptionEnd: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onAudioInterruptionBegin: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onAppShow: {
                          callback: 'CallbackResult'
                        },
                        onAppHide: {
                          callback: 'CallbackResult'
                        },
                        offUnhandledRejection: {
                          callback: 'Result<T>'
                        },
                        offThemeChange: {
                          callback: 'Result'
                        },
                        offPageNotFound: {
                          callback: 'Result'
                        },
                        offLazyLoadError: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offError: {
                          callback: 'string | ErrorEvent | Error'
                        },
                        offAudioInterruptionEnd: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offAudioInterruptionBegin: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offAppShow: {
                          callback: 'CallbackResult'
                        },
                        offAppHide: {
                          callback: 'CallbackResult'
                        },
                        getLaunchOptionsSync: {
                          object: 'void',
                          success: 'void',
                          'return': 'LaunchOptions'
                        },
                        getEnterOptionsSync: {
                          object: 'void',
                          success: 'void',
                          'return': 'EnterOptions'
                        },
                        env: {},
                        arrayBufferToBase64: '*',
                        base64ToArrayBuffer: '*',
                        createCanvasContext: {
                          object: 'string',
                          success: 'void',
                          'return': 'CanvasContext'
                        },
                        canvasToTempFilePath: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<SuccessCallbackResult>'
                        },
                        canvasPutImageData: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        canvasGetImageData: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<SuccessCallbackResult>'
                        },
                        createOffscreenCanvas: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        reportMonitor: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        reportAnalytics: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        reportEvent: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getExptInfoSync: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        stopAccelerometer: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        startAccelerometer: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        onAccelerometerChange: {
                          callback: 'Result'
                        },
                        offAccelerometerChange: {
                          callback: 'Result'
                        },
                        checkIsOpenAccessibility: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getBatteryInfoSync: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getBatteryInfo: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<SuccessCallbackResult>'
                        },
                        stopBluetoothDevicesDiscovery: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        startBluetoothDevicesDiscovery: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        openBluetoothAdapter: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onBluetoothDeviceFound: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onBluetoothAdapterStateChange: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offBluetoothDeviceFound: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offBluetoothAdapterStateChange: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        makeBluetoothPair: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        isBluetoothDevicePaired: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getConnectedBluetoothDevices: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getBluetoothDevices: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getBluetoothAdapterState: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        closeBluetoothAdapter: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        writeBLECharacteristicValue: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        setBLEMTU: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        readBLECharacteristicValue: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onBLEMTUChange: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onBLEConnectionStateChange: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onBLECharacteristicValueChange: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offBLEMTUChange: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offBLEConnectionStateChange: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offBLECharacteristicValueChange: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        notifyBLECharacteristicValueChange: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getBLEMTU: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getBLEDeviceServices: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getBLEDeviceRSSI: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getBLEDeviceCharacteristics: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        createBLEConnection: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        closeBLEConnection: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onBLEPeripheralConnectionStateChanged: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offBLEPeripheralConnectionStateChanged: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        createBLEPeripheralServer: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        addPhoneRepeatCalendar: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        addPhoneCalendar: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        setClipboardData: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<Promised>'
                        },
                        getClipboardData: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<Promised>'
                        },
                        stopCompass: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        startCompass: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        onCompassChange: {
                          callback: 'OnCompassChangeCallbackResult'
                        },
                        offCompassChange: {
                          callback: 'OnCompassChangeCallbackResult'
                        },
                        chooseContact: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        addPhoneContact: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getRandomValues: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        stopGyroscope: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        startGyroscope: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onGyroscopeChange: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offGyroscopeChange: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        stopBeaconDiscovery: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        startBeaconDiscovery: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onBeaconUpdate: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onBeaconServiceChange: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offBeaconUpdate: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offBeaconServiceChange: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getBeacons: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onKeyboardHeightChange: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offKeyboardHeightChange: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        hideKeyboard: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getSelectedTextRange: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onMemoryWarning: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offMemoryWarning: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        stopDeviceMotionListening: {
                          object: 'Option',
                          success: 'void'
                        },
                        startDeviceMotionListening: {
                          object: 'Option',
                          success: 'void'
                        },
                        onDeviceMotionChange: {
                          callback: 'CallbackResult'
                        },
                        offDeviceMotionChange: {
                          callback: 'CallbackResult'
                        },
                        getNetworkType: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<SuccessCallbackResult>'
                        },
                        onNetworkWeakChange: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onNetworkStatusChange: {
                          callback: 'CallbackResult'
                        },
                        offNetworkWeakChange: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offNetworkStatusChange: {
                          callback: 'CallbackResult'
                        },
                        getLocalIPAddress: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        stopHCE: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        startHCE: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        sendHCEMessage: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onHCEMessage: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offHCEMessage: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getNFCAdapter: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getHCEState: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        makePhoneCall: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        scanCode: {
                          object: 'Partial<{ needResult: number; }>',
                          success: 'void',
                          'return': 'Promise<any>'
                        },
                        setVisualEffectOnCapture: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        setScreenBrightness: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        setKeepScreenOn: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onUserCaptureScreen: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offUserCaptureScreen: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getScreenBrightness: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onScreenRecordingStateChanged: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offScreenRecordingStateChanged: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getScreenRecordingState: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        sendSms: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        vibrateShort: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        vibrateLong: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        stopWifi: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        startWifi: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        setWifiList: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onWifiConnectedWithPartialInfo: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onWifiConnected: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onGetWifiList: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offWifiConnectedWithPartialInfo: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offWifiConnected: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offGetWifiList: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getWifiList: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getConnectedWifi: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        connectWifi: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getExtConfigSync: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getExtConfig: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        saveFileToDisk: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        saveFile: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        removeSavedFile: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        openDocument: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getSavedFileList: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getSavedFileInfo: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getFileSystemManager: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getFileInfo: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getApp: {
                          object: '*',
                          success: 'void',
                          'return': 'Instance<T>'
                        },
                        getCurrentInstance: {
                          object: 'void',
                          success: 'void',
                          'return': 'Current'
                        },
                        getLocation: {
                          object: 'Partial<Option>',
                          success: 'void',
                          'return': 'Promise<SuccessCallbackResult>'
                        },
                        css_248z: {},
                        chooseLocation: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<SuccessCallbackResult>'
                        },
                        onLocationChange: '*',
                        offLocationChange: '*',
                        onLocationChangeError: '*',
                        offLocationChangeError: '*',
                        stopLocationUpdate: {
                          object: 'Partial<Option>',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        startLocationUpdate: {
                          object: 'Partial<Option>',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        startLocationUpdateBackground: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        openLocation: {
                          object: 'Partial<{ scale: number; }>',
                          success: 'void',
                          'return': 'Promise<any>'
                        },
                        choosePoi: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getFuzzyLocation: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        stopVoice: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        setInnerAudioOption: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        playVoice: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        pauseVoice: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getAvailableAudioSources: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        createWebAudioContext: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        createMediaAudioPlayer: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        createInnerAudioContext: {
                          object: 'Option',
                          success: 'void',
                          'return': 'InnerAudioContext'
                        },
                        createAudioContext: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        stopBackgroundAudio: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        seekBackgroundAudio: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        playBackgroundAudio: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        pauseBackgroundAudio: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onBackgroundAudioStop: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onBackgroundAudioPlay: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onBackgroundAudioPause: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getBackgroundAudioPlayerState: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getBackgroundAudioManager: {
                          object: 'void',
                          success: 'void',
                          'return': 'BackgroundAudioManager'
                        },
                        createCameraContext: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        saveImageToPhotosAlbum: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        getImageInfo: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<SuccessCallbackResult>'
                        },
                        previewImage: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        chooseImage: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<SuccessCallbackResult>'
                        },
                        previewMedia: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        compressImage: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        chooseMessageFile: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        editImage: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        cropImage: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        createLivePusherContext: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        createLivePlayerContext: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        createMapContext: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        createMediaRecorder: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        stopRecord: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        startRecord: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getRecorderManager: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        saveVideoToPhotosAlbum: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        getVideoInfo: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<SuccessCallbackResult>'
                        },
                        chooseMedia: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<SuccessCallbackResult>'
                        },
                        chooseVideo: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<SuccessCallbackResult>'
                        },
                        openVideoEditor: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        createVideoContext: {
                          object: 'string',
                          success: 'void',
                          'return': 'VideoContext'
                        },
                        compressVideo: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        createVideoDecoder: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        createMediaContainer: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        updateVoIPChatMuteConfig: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        subscribeVoIPVideoMembers: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        setEnable1v1Chat: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onVoIPVideoMembersChanged: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onVoIPChatStateChanged: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onVoIPChatSpeakersChanged: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onVoIPChatMembersChanged: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onVoIPChatInterrupted: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offVoIPChatSpeakersChanged: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offVoIPVideoMembersChanged: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offVoIPChatStateChanged: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offVoIPChatMembersChanged: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offVoIPChatInterrupted: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        joinVoIPChat: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        join1v1Chat: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        exitVoIPChat: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        openEmbeddedMiniProgram: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        navigateToMiniProgram: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        navigateBackMiniProgram: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        exitMiniProgram: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        openBusinessView: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        downloadFile: {
                          object: 'Option',
                          success: 'void',
                          'return': 'DownloadTaskPromise'
                        },
                        stopLocalServiceDiscovery: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        startLocalServiceDiscovery: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onLocalServiceResolveFail: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onLocalServiceLost: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onLocalServiceFound: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onLocalServiceDiscoveryStop: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offLocalServiceResolveFail: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offLocalServiceLost: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offLocalServiceFound: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offLocalServiceDiscoveryStop: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        request: {
                          object: '*',
                          success: 'void',
                          'return': 'RequestTask<T>'
                        },
                        addInterceptor: '*',
                        cleanInterceptors: '*',
                        createTCPSocket: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        createUDPSocket: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        uploadFile: {
                          object: 'Option',
                          success: 'void',
                          'return': 'UploadTaskPromise'
                        },
                        sendSocketMessage: '*',
                        onSocketOpen: '*',
                        onSocketMessage: '*',
                        onSocketError: '*',
                        onSocketClose: '*',
                        connectSocket: '*',
                        closeSocket: '*',
                        getAccountInfoSync: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        chooseAddress: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        authorizeForMiniProgram: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        authorize: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        openCard: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        addCard: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        reserveChannelsLive: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        openChannelsUserProfile: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        openChannelsLive: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        openChannelsEvent: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        openChannelsActivity: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getChannelsShareKey: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getChannelsLiveNoticeInfo: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getChannelsLiveInfo: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        openCustomerServiceChat: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        requestDeviceVoIP: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getDeviceVoIPList: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        checkIsSupportFacialRecognition: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        startFacialRecognitionVerify: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        startFacialRecognitionVerifyAndUploadVideo: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        faceVerifyForPay: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        addVideoToFavorites: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        addFileToFavorites: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getGroupEnterInfo: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        chooseInvoiceTitle: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        chooseInvoice: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        chooseLicensePlate: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        pluginLogin: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        login: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        checkSession: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        checkIsAddedToMyMiniProgram: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        requirePrivacyAuthorize: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        openPrivacyContract: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onNeedPrivacyAuthorization: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getPrivacySetting: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        showRedPackage: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        openSetting: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getSetting: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        startSoterAuthentication: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        checkIsSupportSoterAuthentication: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        checkIsSoterEnrolledInDevice: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        requestSubscribeMessage: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        requestSubscribeDeviceMessage: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getUserProfile: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getUserInfo: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        shareToWeRun: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getWeRunData: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        requestPayment: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        requestPluginPayment: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        requestOrderPayment: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        openQzonePublish: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getQQRunData: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        setOfficialDress: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        setCustomDress: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        updateQQApp: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        addRecentColorSign: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getGuildInfo: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        applyAddToMyApps: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        isAddedToMyApps: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        router: {},
                        updateShareMenu: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        showShareMenu: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        showShareImageMenu: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        shareVideoMessage: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        shareFileMessage: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onCopyUrl: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        offCopyUrl: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        hideShareMenu: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getShareInfo: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        authPrivateMessage: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        setBackgroundFetchToken: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onBackgroundFetchData: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getBackgroundFetchToken: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getBackgroundFetchData: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        createCacheManager: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        setStorageSync: {
                          object: 'string',
                          success: 'void'
                        },
                        setStorage: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        revokeBufferURL: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        removeStorageSync: {
                          object: 'string',
                          success: 'void'
                        },
                        removeStorage: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        getStorageSync: {
                          object: '*',
                          success: 'void',
                          'return': '*'
                        },
                        getStorageInfoSync: {
                          object: 'void',
                          success: 'void',
                          'return': 'Option'
                        },
                        getStorageInfo: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        getStorage: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<SuccessCallbackResult<T>>'
                        },
                        createBufferURL: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        clearStorageSync: {
                          object: 'void',
                          success: 'void'
                        },
                        clearStorage: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        batchSetStorageSync: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        batchSetStorage: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        batchGetStorageSync: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        batchGetStorage: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        setPageInfo: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        ocrIdCard: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        ocrBankCard: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        ocrDrivingLicense: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        ocrVehicleLicense: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        textReview: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        textToAudio: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        imageAudit: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        advancedGeneralIdentify: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        objectDetectIdentify: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        carClassify: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        dishClassify: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        logoClassify: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        animalClassify: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        plantClassify: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getSwanId: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        requestPolymerPayment: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        navigateToSmartGameProgram: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        navigateToSmartProgram: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        navigateBackSmartProgram: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        preloadSubPackage: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        createAnimation: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Animation'
                        },
                        worklet: '*',
                        setBackgroundTextStyle: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        setBackgroundColor: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        nextTick: {
                          callback: 'any[]'
                        },
                        loadFontFace: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        showToast: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        hideToast: {
                          object: 'Option',
                          success: 'void'
                        },
                        showLoading: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        hideLoading: {
                          object: 'Option',
                          success: 'void'
                        },
                        showModal: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<SuccessCallbackResult>'
                        },
                        showActionSheet: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<SuccessCallbackResult>'
                        },
                        enableAlertBeforeUnload: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        disableAlertBeforeUnload: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        getMenuButtonBoundingClientRect: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        showNavigationBarLoading: '*',
                        setNavigationBarTitle: '*',
                        setNavigationBarColor: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        hideNavigationBarLoading: '*',
                        hideHomeButton: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        startPullDownRefresh: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        stopPullDownRefresh: {
                          object: 'Option',
                          success: 'void'
                        },
                        pageScrollTo: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        setTopBarText: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        initTabBarApis: '*',
                        showTabBarRedDot: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        showTabBar: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        setTabBarStyle: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        setTabBarItem: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        setTabBarBadge: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        removeTabBarBadge: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        hideTabBarRedDot: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        hideTabBar: {
                          object: 'Option',
                          success: 'void',
                          'return': 'Promise<CallbackResult>'
                        },
                        setWindowSize: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        onWindowResize: {
                          callback: 'CallbackResult'
                        },
                        offWindowResize: {
                          callback: 'CallbackResult'
                        },
                        checkIsPictureInPictureActive: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        createWorker: {
                          object: '*',
                          success: 'void',
                          'return': 'Promise<Partial<CallbackResult> & Record<string, unknown> & CallbackResult>'
                        },
                        createSelectorQuery: {
                          object: 'void',
                          success: 'void',
                          'return': 'SelectorQuery'
                        },
                        createIntersectionObserver: {
                          object: '*',
                          success: 'void',
                          'return': 'IntersectionObserver'
                        },
                        createMediaQueryObserver: {
                          object: 'void',
                          success: 'void',
                          'return': 'MediaQueryObserver'
                        }
                      },
                      components: {
                        ad: {},
                        'ad-custom': {},
                        'animation-video': {},
                        'animation-view': {},
                        'ar-camera': {},
                        audio: {
                          autoplay: 'boolean',
                          controls: 'boolean',
                          loop: 'boolean',
                          muted: 'boolean',
                          nativeProps: '*',
                          src: 'string'
                        },
                        'aweme-data': {},
                        block: {},
                        button: {
                          disabled: 'boolean',
                          formType: '"submit" | "reset"',
                          hoverClass: 'string',
                          hoverStartTime: 'number',
                          hoverStayTime: 'number',
                          loading: 'boolean',
                          plain: 'boolean',
                          size: 'string',
                          type: 'string'
                        },
                        camera: {},
                        canvas: {
                          canvasId: 'string',
                          height: 'string',
                          nativeProps: '*',
                          width: 'string'
                        },
                        'channel-live': {},
                        'channel-video': {},
                        checkbox: {
                          checked: 'boolean',
                          color: 'string',
                          disabled: 'boolean',
                          id: 'string',
                          name: 'string',
                          nativeProps: '*',
                          value: 'string | number'
                        },
                        'checkbox-group': {
                          name: '*'
                        },
                        'comment-detail': {},
                        'comment-list': {},
                        'contact-button': {},
                        'cover-image': {
                          nativeProps: '*',
                          src: 'string'
                        },
                        'cover-view': {
                          animation: 'string',
                          hoverClass: 'string',
                          hoverStartTime: 'number',
                          hoverStayTime: 'number'
                        },
                        'custom-wrapper': {},
                        'double-tap-gesture-handler': {},
                        'draggable-sheet': {},
                        editor: {},
                        'follow-swan': {},
                        'force-press-gesture-handler': {},
                        form: {},
                        'functional-page-navigator': {},
                        'grid-builder': {},
                        'grid-view': {},
                        'horizontal-drag-gesture-handler': {},
                        icon: {
                          color: 'string',
                          size: 'string | number',
                          type: 'Type'
                        },
                        image: {
                          lazyLoad: 'boolean',
                          mode: 'Mode',
                          nativeProps: '*',
                          src: 'string'
                        },
                        'inline-payment-panel': {},
                        input: {
                          autoFocus: 'boolean',
                          confirmType: 'string',
                          disabled: 'boolean',
                          focus: '() => Promise<void>',
                          maxlength: 'number',
                          name: 'string',
                          nativeProps: '*',
                          password: 'boolean',
                          placeholder: 'string',
                          readonly: 'boolean',
                          type: 'string',
                          value: 'string'
                        },
                        'keyboard-accessory': {},
                        label: {
                          'for': 'string'
                        },
                        lifestyle: {},
                        like: {},
                        'list-builder': {},
                        'list-view': {},
                        'live-player': {},
                        'live-pusher': {},
                        login: {},
                        'long-press-gesture-handler': {},
                        lottie: {},
                        map: {
                          circles: 'MapProps.circle[]',
                          enable3D: 'boolean',
                          enableAutoMaxOverlooking: 'boolean',
                          enableBuilding: 'boolean',
                          enableOverlooking: 'boolean',
                          enableRotate: 'boolean',
                          enableSatellite: 'boolean',
                          enableScroll: 'boolean',
                          enableTraffic: 'boolean',
                          enableZoom: 'boolean',
                          height: 'string',
                          latitude: 'number',
                          layerStyle: 'number',
                          longitude: 'number',
                          markers: 'MapProps.marker[]',
                          maxScale: 'number',
                          minScale: 'number',
                          polygons: 'MapProps.polygon[]',
                          polyline: 'MapProps.polyline[]',
                          rotate: 'number',
                          scale: 'number',
                          showCompass: 'boolean',
                          showScale: 'boolean',
                          skew: 'number',
                          subkey: 'string',
                          width: 'string'
                        },
                        'match-media': {},
                        'movable-area': {
                          scaleArea: 'boolean'
                        },
                        'movable-view': {
                          animation: 'boolean',
                          damping: 'number',
                          direction: '"all" | "vertical" | "horizontal" | "none"',
                          disabled: 'boolean',
                          endScale: '() => Promise<void>',
                          friction: 'number',
                          inertia: 'boolean',
                          outOfBounds: 'boolean',
                          scale: 'boolean',
                          scaleMax: 'number',
                          scaleMin: 'number',
                          scaleValue: 'number',
                          setParent: '({ element, area }: { element: HTMLElement; area: { width: number; height: number; }; }) => Promise<void>',
                          setScale: '(scale: number) => Promise<void>',
                          x: 'string | number',
                          y: 'string | number'
                        },
                        'native-slot': {},
                        'navigation-bar': {},
                        navigator: {
                          delta: 'number',
                          hoverClass: 'string',
                          isHover: 'boolean',
                          openType: 'string',
                          url: 'string'
                        },
                        'nested-scroll-body': {},
                        'nested-scroll-header': {},
                        'official-account': {},
                        'open-container': {},
                        'open-data': {},
                        'page-container': {},
                        'page-meta': {},
                        'pan-gesture-handler': {},
                        picker: {
                          disabled: 'boolean',
                          end: 'string',
                          fields: 'Fields',
                          mode: 'Mode',
                          name: 'string',
                          range: 'any[]',
                          rangeKey: 'string',
                          start: 'string',
                          textProps: 'PickerText',
                          value: 'PickerValue'
                        },
                        'picker-view-column': {
                          col: 'string',
                          initialPosition: 'string',
                          paddingVertical: 'number'
                        },
                        'picker-view': {
                          indicatorClass: 'string',
                          indicatorStyle: 'string',
                          maskClass: 'string',
                          maskStyle: 'string',
                          value: 'number[]'
                        },
                        progress: {
                          active: 'boolean',
                          activeColor: 'string',
                          backgroundColor: 'string',
                          borderRadius: 'string | number',
                          fontSize: 'string | number',
                          percent: 'number',
                          showInfo: 'boolean',
                          strokeWidth: 'string | number'
                        },
                        'pull-to-refresh': {
                          damping: 'number',
                          distanceToRefresh: 'number',
                          indicator: '{ activate: string; deactivate: string; release: string; finish: string; }',
                          prefixCls: 'string'
                        },
                        radio: {
                          checked: 'boolean',
                          disabled: 'boolean',
                          id: 'string',
                          name: 'string',
                          nativeProps: '*',
                          value: 'string'
                        },
                        'radio-group': {
                          name: '*'
                        },
                        'rich-text': {
                          nodes: 'Nodes',
                          selectable: 'boolean',
                          space: 'string | number | symbol',
                          userSelect: 'boolean'
                        },
                        'root-portal': {},
                        'rtc-room': {},
                        'rtc-room-item': {},
                        'scale-gesture-handler': {},
                        script: {},
                        'scroll-view': {
                          animated: 'boolean',
                          enhanced: 'boolean',
                          lowerThreshold: 'string | number',
                          mpScrollIntoView: 'string',
                          mpScrollIntoViewAlignment: '"center" | "start" | "end" | "nearest"',
                          mpScrollIntoViewMethod: '(selector: string) => Promise<void>',
                          mpScrollLeft: 'string | number',
                          mpScrollToMethod: '(object: Option) => Promise<void>',
                          mpScrollTop: 'string | number',
                          scrollX: 'boolean',
                          scrollY: 'boolean',
                          showScrollbar: 'boolean',
                          upperThreshold: 'string | number'
                        },
                        'share-element': {},
                        slider: {
                          activeColor: 'string',
                          backgroundColor: 'string',
                          blockColor: 'string',
                          blockSize: 'number',
                          disabled: 'boolean',
                          max: 'number',
                          min: 'number',
                          name: 'string',
                          showValue: 'boolean',
                          step: 'number',
                          value: 'number'
                        },
                        slot: {},
                        snapshot: {},
                        span: {},
                        'sticky-header': {},
                        'sticky-section': {},
                        swiper: {
                          autoplay: 'boolean',
                          circular: 'boolean',
                          current: 'number',
                          currentItemId: 'string',
                          displayMultipleItems: 'number',
                          duration: 'number',
                          effectsProps: 'Record<string, any>',
                          full: 'boolean',
                          indicatorActiveColor: 'string',
                          indicatorColor: 'string',
                          indicatorDots: 'boolean',
                          interval: 'number',
                          nextMargin: 'string',
                          previousMargin: 'string',
                          vertical: 'boolean',
                          zoom: 'boolean'
                        },
                        'swiper-item': {
                          itemId: 'string'
                        },
                        'switch': {
                          checked: 'boolean',
                          color: 'string',
                          disabled: 'boolean',
                          name: 'string',
                          nativeProps: '*',
                          type: 'string'
                        },
                        'tab-item': {},
                        tabs: {},
                        'tap-gesture-handler': {},
                        text: {
                          numberOfLines: 'number',
                          selectable: 'boolean',
                          space: 'string | number | symbol',
                          userSelect: 'boolean'
                        },
                        textarea: {
                          autoFocus: 'boolean',
                          autoHeight: 'boolean',
                          disabled: 'boolean',
                          focus: '() => Promise<void>',
                          maxlength: 'number',
                          name: 'string',
                          nativeProps: '*',
                          placeholder: 'string',
                          value: 'string'
                        },
                        'vertical-drag-gesture-handler': {},
                        video: {
                          autoplay: 'boolean',
                          controls: 'boolean',
                          danmuBtn: 'boolean',
                          danmuList: '[]',
                          duration: 'number',
                          enableDanmu: 'boolean',
                          enablePlayGesture: 'boolean',
                          enableProgressGesture: 'boolean',
                          exitFullScreen: '() => Promise<void>',
                          getHlsObject: '() => Promise<HLS>',
                          initialTime: 'number',
                          loop: 'boolean',
                          muted: 'boolean',
                          nativeProps: '*',
                          objectFit: '"contain" | "fill" | "cover"',
                          pause: '() => Promise<void>',
                          play: '() => Promise<void>',
                          poster: 'string',
                          requestFullScreen: '() => Promise<void>',
                          seek: '(position: number) => Promise<void>',
                          showCenterPlayBtn: 'boolean',
                          showFullscreenBtn: 'boolean',
                          showMuteBtn: 'boolean',
                          showPlayBtn: 'boolean',
                          showProgress: 'boolean',
                          src: 'string',
                          stop: '() => Promise<void>',
                          vslideGesture: 'boolean',
                          vslideGestureInFullscreen: 'boolean'
                        },
                        view: {
                          animation: 'string',
                          hoverClass: 'string',
                          hoverStartTime: 'number',
                          hoverStayTime: 'number'
                        },
                        'voip-room': {},
                        'web-view': {
                          src: 'string'
                        }
                      }
                    }
                  }
                ]
              ]
            }
          }
        ]
      },
      /* config.module.rule('media') */
      {
        test: /\.(mp4|webm|ogg|mp3|m4a|wav|flac|aac)(\?.*)?$/,
        type: 'asset',
        parser: {
          dataUrlCondition: {
            maxSize: 10240
          }
        },
        generator: {
          emit: undefined,
          outputPath: undefined,
          publicPath: undefined,
          filename: function () { /* omitted long function */ }
        }
      },
      /* config.module.rule('font') */
      {
        test: /\.(woff2?|eot|ttf|otf)(\?.*)?$/,
        type: 'asset',
        parser: {
          dataUrlCondition: {
            maxSize: 10240
          }
        },
        generator: {
          emit: undefined,
          outputPath: undefined,
          publicPath: undefined,
          filename: function () { /* omitted long function */ }
        }
      },
      /* config.module.rule('image') */
      {
        test: /\.(png|jpe?g|gif|bpm|svg|webp)(\?.*)?$/,
        type: 'asset',
        parser: {
          dataUrlCondition: {
            maxSize: 2048
          }
        },
        generator: {
          emit: undefined,
          outputPath: undefined,
          publicPath: undefined,
          filename: function () { /* omitted long function */ }
        }
      },
      /* config.module.rule('process-import-taro-h5') */
      {
        test: /taro-h5[\\/]dist[\\/](api[\\/]taro|index\.esm)/,
        loader: 'C:\\Code\\FamilyClaw\\apps\\user-app\\node_modules\\@tarojs\\plugin-framework-react\\dist\\api-loader.js'
      },
      /* config.module.rule('map') */
      {
        test: /\.map$/,
        type: 'json'
      }
    ]
  },
  optimization: {
    minimize: true,
    nodeEnv: 'production',
    chunkIds: 'deterministic',
    removeEmptyChunks: true,
    splitChunks: {
      chunks: 'initial',
      hidePathInfo: true,
      minSize: 0,
      cacheGroups: {
        'default': false,
        defaultVendors: false,
        common: {
          name: false,
          minChunks: 2,
          priority: 1
        },
        vendors: {
          name: false,
          minChunks: 2,
          test: function () { /* omitted long function */ },
          priority: 10
        },
        taro: {
          name: false,
          test: (module) => helper_1.REG_TARO_SCOPED_PACKAGE.test(module.context),
          priority: 100
        }
      }
    },
    minimizer: [
      /* config.optimization.minimizer('terserPlugin') */
      new TerserPlugin(
        {
          parallel: true,
          terserOptions: {
            keep_fnames: true,
            output: {
              comments: false,
              keep_quoted_props: true,
              quote_keys: true,
              beautify: false
            },
            warnings: false
          }
        }
      ),
      /* config.optimization.minimizer('cssoWebpackPlugin') */
      new CssMinimizerPlugin(
        {
          test: /\.(css|scss|sass|less|styl|stylus|wxss|acss|ttss|jxss|qss)(\?.*)?$/,
          parallel: true,
          minify: function () { /* omitted long function */ },
          minimizerOptions: {
            preset: [
              'default',
              {
                mergeRules: false,
                mergeIdents: false,
                reduceIdents: false,
                discardUnused: false,
                minifySelectors: false
              }
            ]
          }
        }
      )
    ]
  },
  plugins: [
    /* config.plugin('webpackbar') */
    new TaroWebpackBarPlugin(
      {
        reporters: [
          'basic',
          'fancy',
          {
            done: function () { /* omitted long function */ }
          }
        ],
        basic: false,
        fancy: true
      }
    ),
    /* config.plugin('definePlugin') */
    new DefinePlugin(
      {
        'process.env.FRAMEWORK': '"react"',
        'process.env.TARO_ENV': '"h5"',
        'process.env.TARO_PLATFORM': '"web"',
        'process.env.TARO_VERSION': '"4.1.11"',
        'process.env.SUPPORT_TARO_POLYFILL': '"disabled"',
        'process.env.SUPPORT_DINGTALK_NAVIGATE': '"disabled"',
        DEPRECATED_ADAPTER_COMPONENT: 'false'
      }
    ),
    /* config.plugin('mainPlugin') */
    new TaroH5Plugin(
      {
        appPath: 'C:\\Code\\FamilyClaw\\apps\\user-app',
        sourceDir: 'C:\\Code\\FamilyClaw\\apps\\user-app\\src',
        entryFileName: 'app',
        framework: 'react',
        frameworkExts: [
          '.js',
          '.jsx',
          '.ts',
          '.tsx'
        ],
        routerConfig: {
          mode: 'browser'
        },
        runtimePath: '@tarojs/plugin-platform-h5/dist/runtime',
        pxTransformConfig: {
          platform: 'h5',
          designWidth: 750
        },
        alias: {
          '@': 'C:\\Code\\FamilyClaw\\apps\\user-app\\src'
        },
        defineConstants: {},
        prebundle: false,
        isBuildNativeComp: false,
        noInjectGlobalStyle: false,
        modifyAppConfig: undefined,
        onCompilerMake: undefined,
        onParseCreateElement: undefined,
        loaderMeta: {
          importFrameworkStatement: '\nimport * as React from \'react\'\nimport ReactDOM from \'react-dom/client\'\n',
          mockAppStatement: '\nclass App extends React.Component {\n  render () {\n    return this.props.children\n  }\n}\n',
          frameworkArgs: 'React, ReactDOM, config',
          creator: 'createReactApp',
          creatorLocation: '@tarojs/plugin-framework-react/dist/runtime',
          importFrameworkName: 'React',
          extraImportForWeb: 'import { findDOMNode, render, unstable_batchedUpdates } from \'react-dom\'\nimport { defineCustomElementTaroPullToRefreshCore } from \'@tarojs/components/dist/components\'\n',
          execBeforeCreateWebApp: 'Object.assign(ReactDOM, { findDOMNode, render, unstable_batchedUpdates })\ndefineCustomElementTaroPullToRefreshCore()\n',
          modifyConfig(config, source) {
              Object.assign(config, addConfig(source));
          }
        }
      }
    ),
    /* config.plugin('miniCssExtractPlugin') */
    new MiniCssExtractPlugin(
      {
        filename: 'css/[name].css',
        chunkFilename: 'css/[name].css'
      }
    )
  ],
  entry: {
    app: [
      'C:\\Code\\FamilyClaw\\apps\\user-app\\src\\app.config'
    ]
  }
}
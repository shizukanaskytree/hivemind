需要让一个分块的模型先跑起来, 作为 trainer

```
parameter server
      ▲
      │
      │
      │
      │
 trainer server
```

缺少 param server 中类似 push pull average 等的组件.

```
                        parameter server

                              ▲
                              │
                              │
                              │
                              │

client to start ─────►   trainer server
```

这个和原来的模式也不同. 目前已经不需要 client 来启动 trainer server 了. 两者之间不需要传输 activation function.


```
                        ┌──────────────────┐
                        │ parameter server │
                        └──────────────────┘
                                ▲
                                │
                                │
                                │
┌───────────────────────────────┴──────────┐
│                                          │
│ client to start ◄────►   trainer server  │
│                                          │
└──────────────────────────────────────────┘
```


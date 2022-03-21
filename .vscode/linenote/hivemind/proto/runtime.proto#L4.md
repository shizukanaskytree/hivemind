# ConnectionHandler

```
service ConnectionHandler {
  // Listens to incoming requests for expert computation
  rpc info(ExpertUID) returns (ExpertInfo);
  rpc forward(ExpertRequest) returns (ExpertResponse);
  rpc backward(ExpertRequest) returns (ExpertResponse);
}
```

This is more suitable for me to do parameter server.

对于 asyncio 我需要下载本书学习一下, 否则无法运用.
# 实例化

```py
    def get_stub(self, peer: PeerID) -> AuthRPCWrapper:
        """get a stub that sends requests to a given peer"""
        stub = super().get_stub(self.p2p, peer)
        return AuthRPCWrapper(stub, AuthRole.CLIENT, self.authorizer, service_public_key=None)
```

## inputs

```py
peer

<libp2p.peer.id.ID (QmQAFagurooqVTo7VWksuKKsg7myvbLaJuhpuhHZCKN1sN)>
special variables:
function variables:
xor_id: 94525585707003030681884726076604816444386928323352398883724266422675382316128
_b58_str: 'QmQAFagurooqVTo7VWksuKKsg7myvbLaJuhpuhHZCKN1sN'
_bytes: b'\x12 \x1b\rj;\x98\x84&\xd4F\xda\x07\xb4\xb7j\x05t->rT/\x0e\xb6\xa6\xf0S\xcd\xcak1e\xb1'
_xor_id: 94525585707003030681884726076604816444386928323352398883724266422675382316128
```

## temp vars

```
stub
<hivemind.p2p.servicer.DHTProtocolStub object at 0x7f5cc2742160>
special variables:
function variables:
_namespace: None
_p2p: <hivemind.p2p.p2p_daemon.P2P object at 0x7f5cc2747b80>
_peer: <libp2p.peer.id.ID (QmQAFagurooqVTo7VWksuKKsg7myvbLaJuhpuhHZCKN1sN)>

```

## outputs


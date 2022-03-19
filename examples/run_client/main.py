import torch
import hivemind
from hivemind.moe.server.dht_handler import get_experts

dht = hivemind.DHT(initial_peers=["/ip4/127.0.0.1/tcp/38134/p2p/QmRpcu9CogHoahXu6vJAFkhPjBHyBsuoKMX3vQzHKyKHp9"], start=True)
# note: listen=False means that your peer will operate in "client only" mode: 
# this means that it can request other peers, but will not accept requests in return 

expert1, expert4 = get_experts(dht, ["expert.1", "expert.4"])
assert expert1 is not None and expert4 is not None, "server hasn't declared experts (yet?)"

dummy = torch.randn(3, 512)
out = expert1(dummy)  # forward pass
out.sum().backward()  # backward pass

# generate dummy data
x = torch.randn(3, 512)
y = 0.01 * x.sum(dim=-1, keepdim=True)

# local torch module
proj_out = torch.nn.Sequential(
    torch.nn.Linear(512, 3)
)
opt = torch.optim.SGD(proj_out.parameters(), lr=0.01)

for i in range(10):
    prediction = proj_out(expert1(expert4(x)))
    loss = torch.mean(abs(prediction - y))
    print(loss.item())
    opt.zero_grad()
    loss.backward()
    opt.step()
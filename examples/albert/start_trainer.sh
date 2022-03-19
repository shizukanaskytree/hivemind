IP=/ip4/192.168.0.19/tcp/41219/p2p/QmXiig2btWoVDc5msaknTvn2T9sz2VkJQPoi7ojADLHyWc

CUDA_VISIBLE_DEVICES=0 python run_trainer.py \
--per_device_train_batch_size 1 \
--initial_peers ${IP}
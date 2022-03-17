IP=/ip4/192.168.0.19/tcp/42746/p2p/QmQXBTpMH5U326Mnn4jFjyKFDMLAUTadMLK9YcQ4QMmnSF

CUDA_VISIBLE_DEVICES=0 python run_trainer.py \
--per_device_train_batch_size 1 \
--initial_peers ${IP}
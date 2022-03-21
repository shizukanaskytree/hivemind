IP=/ip4/192.168.0.19/tcp/43238/p2p/QmRMV8kuUdtcER5Qq138nVPuptPSV4MWDh2pUzqT34YWYY

CUDA_VISIBLE_DEVICES=0 python run_trainer.py \
--per_device_train_batch_size 1 \
--initial_peers ${IP}
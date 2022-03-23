IP=/ip4/192.168.0.19/tcp/40857/p2p/QmXxnEb82tKmYReJS4Y5kxfTwcqA4rs4iteRNyVP4TDEEr

CUDA_VISIBLE_DEVICES=0 python run_trainer.py \
--per_device_train_batch_size 1 \
--initial_peers ${IP}
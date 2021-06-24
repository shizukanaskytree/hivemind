# Run a master node

```
python run_first_peer.py --dht_listen_on '[::]:*' --experiment_prefix gpt2 --wandb_project gpt-run
```

# Run a trainer node

`ip:port` is from the master node: `Running DHT root at 129.107.208.94:43357`

```
HIVEMIND_THREADS=64 python run_trainer.py \
 --experiment_prefix gpt2 --initial_peers ip:port --seed 42 \
 --logging_first_step --logging_steps 10  --output_dir ./outputs --overwrite_output_dir --logging_dir ./logs \
 --raw_train_csv="data/sample_data.csv" \
 --saved_token_train="data/tokenized_train.csv" \
 --batch_size=8 \
 --make_tokenize \
 --make_tensorboard \
 --epochs=20 \
 --save_epoch=5 \
 --save_path="saved_model"
```
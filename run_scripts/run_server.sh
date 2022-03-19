
python ../hivemind/hivemind_cli/run_server.py \
    --expert_cls ffn \
    --hidden_dim 512 \
    --num_experts 5 \
    --expert_pattern "expert.[0:5]" \
    --listen_on 0.0.0.0:1337

# notes
# https://learning-at-home.readthedocs.io/en/0.9.5/user/quickstart.html#

# How to execute?
# (hm_master) wxf@seir19:~/hm_prj/hm_master/hivemind/run_scripts$ bash run_server.sh 

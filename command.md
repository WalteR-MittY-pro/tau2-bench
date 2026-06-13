# 单任务
tau2 run --domain airline --agent-llm openai/minimax-m3 --user-llm openai/minimax-m3 --num-trials 1 --num-tasks 5 

# 单airline域
tau2 run \
  --domain airline \
  --agent-llm openai/minimax-m3 \
  --user-llm openai/minimax-m3 \
  --num-trials 1 \
  --max-steps 50 \
  --max-concurrency 3 \
  --seed 300 \
  --save-to baseline_airline_gpt54mini \
  --log-level WARNING

# 全量
for DOMAIN in airline retail telecom; do
  tau2 run \
    --domain $DOMAIN \
    --agent-llm openai/minimax-m3\
    --user-llm openai/minimax-m3 \
    --num-trials 1 \
    --max-steps 50 \
    --max-concurrency 3 \
    --save-to baseline_minimax_m3 \
    --log-level WARNING
done
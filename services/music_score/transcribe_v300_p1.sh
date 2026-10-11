#!/bin/bash
cd /home/joons/.hermes/services/music_score
PY=~/guitar-tab/.venv/bin/python
PROMPT="이 악보 조각을 전사. 형식: 마디N: T: <트레블> | B: <베이스>. 음표: 음이름+옥타브+길이 (G4.8=8분, C5.4=4분, G4.2=2분, A4.4d=4분부점, r8/r4/r2=쉼, < > = 오토). 실제로 보이는 것만, 불확실하면 (?). 설명 없이 전사만."
for f in v300/b1_1_0.png v300/b1_1_1.png v300/b1_2_0.png v300/b1_2_1.png v300/b1_3_0.png v300/b1_3_1.png v300/b1_4_0.png v300/b1_4_1.png v300/b1_5_0.png v300/b1_5_1.png; do
  echo "===== $f ====="
  for attempt in 1 2 3; do
    out=$($PY vision_test.py "$f" "$PROMPT" 2>&1)
    if ! echo "$out" | grep -q "^ERR"; then echo "$out"; break; fi
    echo "[retry $attempt: $out]"; sleep 15
  done
done

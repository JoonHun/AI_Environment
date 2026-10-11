#!/bin/bash
# usage: batch_transcribe.sh s1_1 s1_2
cd /home/joons/.hermes/services/music_score
PROMPT="이 악보 스트립을 전사. 형식 엄격 준수:
마디N: T: <음표들> | B: <베이스 음표들>
음표 형식: 음이름+옥타브+길이 (예: G4.8 = G4 8분음표, C5.4, G4.2, E4.4d = 8분부점, r8=8분쉼, r4=4분쉼)
트레블은 T:, 베이스는 B: 에 각각. 불확실한 음은 뒤에 (?) 붙여.
마디 번호는 이 조각 안의 실제 번호. 설명 문장 금지, 전사만 출력."
for s in "$@"; do
  echo "===== STRIP $s ====="
  ~/guitar-tab/.venv/bin/python vision_test.py "pdf2tab/$s.png" "$PROMPT"
done

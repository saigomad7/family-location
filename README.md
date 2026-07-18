# 우리 가족 위치 (Family Location)

엄마·아빠·딸이 서로의 위치를 확인하는 모바일 웹앱입니다.
가족 모두의 동의 하에, 학원 오가는 길 안전 확인 용도로 만들었습니다.

- 프론트엔드: HTML 단일 파일 + Leaflet 지도 → **GitHub Pages** 배포
- 위치 동기화: **Firebase Realtime Database** (무료 Spark 플랜)

> ⚠️ **웹앱의 한계**: 화면이 꺼지거나 브라우저를 닫으면 위치 전송이 멈춥니다.
> "필요할 때 켜서 서로 확인하는" 용도이며, 상시 추적이 필요하면
> Google 지도의 위치공유 기능을 병행하세요.

---

## 1. Firebase 설정 (최초 1회)

1. https://console.firebase.google.com 접속 → **프로젝트 추가** (이름 예: `family-location`)
2. 왼쪽 메뉴 **빌드 → Realtime Database → 데이터베이스 만들기**
   - 위치: `asia-southeast1` (싱가포르)
   - 보안 규칙: 일단 "잠금 모드"로 시작
3. Realtime Database → **규칙** 탭에 아래를 붙여넣고 게시:

```json
{
  "rules": {
    ".read": false,
    ".write": false,
    "families": {
      "$family": {
        ".read": true,
        ".write": true
      }
    }
  }
}
```

> 루트 읽기를 막았기 때문에, 정확한 가족 코드(경로)를 아는 사람만 접근할 수 있습니다.

4. 프로젝트 설정(톱니바퀴) → **일반 → 내 앱 → 웹 앱 추가(`</>`)** → 앱 등록
5. 화면에 나오는 `firebaseConfig` 값을 복사해서 `index.html`의
   `firebaseConfig` 부분(`REPLACE_ME` 자리)에 붙여넣기
   - `databaseURL`이 없으면 Realtime Database 페이지 상단의 URL을 복사해서 추가

> `firebaseConfig`의 apiKey는 원래 공개되는 값이라 GitHub에 올라가도 괜찮습니다.
> 접근 제어는 위의 규칙 + 가족 코드가 담당합니다.

## 2. GitHub Pages 배포

```bash
cd ~/family_location
git add -A && git commit -m "Firebase config 입력"
gh repo create family-location --public --source=. --push
```

GitHub 저장소 → **Settings → Pages → Branch: main, / (root)** 선택 → 저장.
1~2분 후 `https://saigomad7.github.io/family-location/` 에서 접속 가능.

> Pages는 HTTPS라서 브라우저 위치 권한(Geolocation)이 정상 동작합니다.

## 3. 가족 폰에 설치

1. 각자 폰에서 위 주소 접속
2. **가족 코드 입력**: 가족끼리만 아는 6자 이상 문자열 (예: 랜덤 20자 추천).
   셋 다 **똑같이** 입력해야 같은 지도에 보입니다.
   코드는 각자 폰에만 저장되며 GitHub에는 올라가지 않습니다.
3. 자기 역할(엄마/아빠/딸) 선택
4. 홈 화면에 추가: iPhone은 Safari 공유 → "홈 화면에 추가",
   Android는 Chrome 메뉴 → "홈 화면에 추가"
5. "내 위치 공유 시작"을 누르면 위치 권한 요청 → **허용**

## 4. 사용 방법

- **내 위치 공유 시작/중지**: 켜져 있는 동안 8초마다 위치를 전송 (화면 꺼짐 방지 wake lock 포함)
- 하단 카드에서 각 가족의 마지막 위치 시각 확인, 카드를 누르면 지도가 그 사람 위치로 이동
- 딸이 학원 갈 때 공유를 켜두면 엄마·아빠가 실시간으로 확인 가능

## 파일 구성

| 파일 | 설명 |
|---|---|
| `index.html` | 앱 전체 (지도 + Firebase 연동 + UI) |
| `manifest.json` | 홈 화면 설치(PWA)용 매니페스트 |

# AI Agent Email Disclaimer

## Requirement
All emails sent via smtp_sender.py must include automatic disclaimer footer stating the email is auto-sent by AI Agent and replies are unprocessed.

## Bilingual Footer Content

### HTML Footer
```html
<br><br>
<hr>
<p style="font-size:12px;color:#666;">
이 메일은 AI Agent에 의해 자동 발송되었습니다. 직접 회신하셔도 답변이 불가합니다.<br>
This email was sent automatically by AI Agent. Replies will not be processed.<br>
문의사항은 joonhun.shin@gmail.com으로 연락 주세요.<br>
For inquiries, please contact joonhun.shin@gmail.com.
</p>
```

### Plain Text Footer
```
---

이 메일은 AI Agent에 의해 자동 발송되었습니다. 직접 회신하셔도 답변이 불가합니다.
This email was sent automatically by AI Agent. Replies will not be processed.
문의사항은 joonhun.shin@gmail.com으로 연락 주세요.
For inquiries, please contact joonhun.shin@gmail.com.
```

## Implementation
- HTML emails: Footer appended before </body> or </html> tag
- Plain text emails: Footer appended at end
- Automatically inserted by smtp_sender.py send_email function
- No manual intervention required

## User Context
User specifically requested automatic footer addition to prevent replies to AI-generated emails. Footer must be bilingual Korean/English.

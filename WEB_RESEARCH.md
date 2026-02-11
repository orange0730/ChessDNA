# Web research log (ChessDNA)

規則：每次使用網路查資料（web_search/web_fetch），都在此追加：日期時間、查詢/URL、摘要結論、關鍵連結。

---

## 2026-02-12

### Cloudflare Pages — custom domains
- Source: https://developers.cloudflare.com/pages/configuration/custom-domains/
- Notes:
  - 在 Cloudflare Dashboard → Workers & Pages → 選 Pages project → Custom domains → Set up a domain。
  - 若綁 apex/root domain（example.com），需要把該網域加入 Cloudflare zone，並把 nameservers 指到 Cloudflare；Cloudflare 會自動建立所需的 CNAME record。
  - 若用子網域（shop.example.com），不一定要整個網域都在 Cloudflare，但需要在 DNS provider 建 CNAME 指向 `<YOUR_SITE>.pages.dev`。
  - CAA records 可能會阻擋 Cloudflare 發證書，需要允許 letsencrypt/ssl.com 等。

### Domain / portfolio TLD discussions (informal)
- DEV Community: Which domain name to choose for portfolio
  - https://dev.to/koladev/which-domain-name-to-choose-for-portfolio-website-4nnl
  - takeaways: .dev 對開發者作品集合理；.com 仍通用。
- DEV Community: tips choosing .dev or .com
  - https://dev.to/codebucks/what-are-your-tips-on-choosing-domain-name-dev-or-com-j2f
  - takeaways: .dev 在開發者圈接受度高。
- Reddit (webhosting): .dev + .com 轉址策略
  - https://www.reddit.com/r/webhosting/comments/j8iu5c/which_domain_to_choose_for_my_personal_web/
  - takeaways: 可用 .dev 當主站，.com 轉址到 .dev（避免別人誤打 .com）。

### Cloudflare Registrar pricing references
- Cloudflare at-cost pricing reference table:
  - https://cfdomainpricing.com/
- Cloudflare official: Registrar (no markup)
  - https://www.cloudflare.com/products/registrar/


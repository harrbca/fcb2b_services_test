
# fcB2B Request Signing – High-Level Overview

fcB2B web services require a custom **HMAC-SHA256** signature to ensure each request is authentic and untampered.  
Here’s the signing process at a high level.

---

## 1️ Build the Required Query Parameters

Every fcB2B request must include:

- **GlobalIdentifier** — UUID for this request  
- **TimeStamp** — UTC timestamp (`YYYY-MM-DDTHH:MM:SSZ`)  
- **apiKey** — your assigned API key  
- **Service-specific parameters** — e.g., `SupplierItemSKU`

---

## 2 Canonicalize the Query String

Canonicalization ensures both parties sign the *same* bytes.

1. Sort all parameters **lexicographically** by parameter name  
2. Percent-encode names and values using **RFC3986 rules**  
3. Build one string:
   ```
   Key1=Value1&Key2=Value2&...
   ```

Example:

```
GlobalIdentifier=...&SupplierItemSKU=...&TimeStamp=...&apiKey=anonymous
```

---

## 3️ Build the `StringToSign`

The signature is always computed from this exact 4-line format:

```
GET
{host}
{path}
{canonicalQueryString}
```

For example:

```
GET
des.buckwold.com
/danciko/bwl/dancik-b2b/fcb2b/StockCheck
GlobalIdentifier=...&SupplierItemSKU=...&TimeStamp=...&apiKey=anonymous
```

The newline characters must be exact — no extra spaces.

---

## 4 Compute HMAC-SHA256

Use your **SECRET_KEY** to compute:

```
HMAC_SHA256(secretKey, StringToSign)
```

Then **Base64-encode** the binary output.

---

## 5 Percent-Encode the Base64 Signature

Because Base64 contains characters not safe for URLs (`+ / =`), you percent-encode it again using RFC3986 rules.

---

## 6️ Append the Signature to the Final URL

```
https://{host}{path}?{canonicalQueryString}&Signature={encodedSignature}
```

This final URL is what you send via HTTP GET.

---

# ✔ Summary (Ultra-Short)

1. Build query params  
2. Sort + RFC3986-encode  
3. Create `StringToSign`  
4. HMAC-SHA256 with secret key  
5. Base64 → percent-encode  
6. Append `Signature=` to query string  


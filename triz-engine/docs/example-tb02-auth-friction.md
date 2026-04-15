# Walkthrough: TB-02 — Multi-Factor Authentication UX Friction

Step-by-step illustration of **`/triz:analyze`** on **TB-02** (mobile banking authentication). Ground-truth IDs match `benchmark/problems/TB-02.json`.

## 1. Problem statement

From the benchmark:

> A mobile banking application serving 8 million users requires strong authentication to meet PCI-DSS and SOC 2 compliance. Each additional authentication step (password, SMS OTP, biometric, device attestation) reduces unauthorized access attempts by approximately 35%, but also causes a 23% user drop-off per step.
>
> The current 3-step flow (password → SMS OTP → biometric) achieves a 0.001% fraud rate but has a 47% login completion rate, with customer support costs for locked-out users reaching $2.1M annually.
>
> The security team mandates at minimum 3 authentication factors, while the product team demands above 90% login completion rate.
>
> Simply reducing steps weakens security below regulatory thresholds, while maintaining steps continues hemorrhaging users.

## 2. Running `/triz:analyze`

### Expected flow

1. **Classification — Technical contradiction**  
   Improving **security strength** worsens **ease of use / completion** (and vice versa). The stakeholder framing is not “be both infinitely strong and zero friction at the same instant” but a **paired degradation**: more factors → fewer completed logins.

2. **Parameter mapping (canonical TB-02)**  
   - **14 — Strength** (resistance to attack, assurance of identity)  
   - **33 — Ease of operation** (low friction, high completion)

3. **Matrix lookup** — TRIZBENCH **target** principles for TB-02 are **6 (Universality)**, **10 (Preliminary action)**, **13 (The other way around)**.  
   **Repository note:** `lookup_matrix(14, 33)` in `data/triz-matrix.json` returns **`[32, 40, 25, 2]`**; expert or hybrid selection may diverge from the classical cell. The sketches below use the benchmark targets.

4. **Solution sketches (mobile banking)**

   | Principle | Sketch |
   |-----------|--------|
   | **6 — Universality** | One **universal trust surface**: FIDO2/WebAuthn passkeys replace SMS OTP as the “something you have,” using the same biometric gate for both possession and inherence where policy allows; one device-bound key satisfies multiple factor *classes* without three separate UX steps. |
   | **10 — Preliminary action** | **Risk-based step-up** decided *before* the heavy UI path: silent device attestation, app integrity, and behavioral signals run in the background; only high-risk sessions surface the third factor. Low-risk sessions complete in one or two visible steps while still meeting “3 factors” over the session lifecycle. |
   | **13 — The other way around** | Invert the flow: instead of “user proves everything every time,” the **bank proves the channel** (bound device, secure enclave, push-to-approve with cryptographic signing) so the user performs **one** deliberate act that implicitly carries multiple factors. |

5. **Evaluator scoring** — Sketches are judged on whether they **eliminate** the contradiction (strong assurance without three sequential pain steps), **novel_combination** vs **standard** patterns, and IFR fit (minimal extra cost, self-enforcing security, few side effects). Universality + preliminary action often score well together.

6. **Top recommendation (illustrative)**  
   **Passkey-first authentication with invisible preliminary risk checks:** register passkeys as the primary path; use server-side risk scoring and device binding *before* showing UI; reserve SMS or manual review for tail risk only. This preserves multi-factor assurance while collapsing perceived steps for the majority of users — targeting the product team’s completion goal without dropping below policy intent.

---

**Ground truth reference:** `benchmark/problems/TB-02.json` (`technical`, parameters **14** / **33**, principles **6, 10, 13**).

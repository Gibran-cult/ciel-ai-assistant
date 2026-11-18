import { TEXT } from "./strings";

export function SignedOut({ consentRequired, failed, onLogin }: { consentRequired: boolean; failed: boolean; onLogin: () => void }) {
  return (
    <section className="block" aria-labelledby="signin-title">
      <h2 id="signin-title" className="section-title">{TEXT.signIn}</h2>
      <p className="note">{consentRequired ? TEXT.consentRequired : TEXT.signInIntro}</p>
      {failed && <p className="error" role="alert">{TEXT.signInFailed}</p>}
      <button type="button" className="primary" onClick={onLogin}>{TEXT.signIn}</button>
    </section>
  );
}

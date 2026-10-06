import { useNavigate } from "@tanstack/react-router";
import { type SubmitEvent, useState } from "react";

import { AlertIcon } from "../../components/AlertIcon";
import { Logo } from "../../components/Logo";

import { signInErrorMessage, useLogin } from "./hooks";

/** Sign-in screen: email and password, one primary action (Design.md section 7.1). */
export function SignInPage() {
  const navigate = useNavigate();
  const signIn = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  function onSubmit(event: SubmitEvent<HTMLFormElement>) {
    event.preventDefault();
    signIn.mutate(
      { email: email.trim(), password },
      {
        onSuccess: (session) =>
          void navigate({ to: session.user.role === "interviewer" ? "/me/candidates" : "/" }),
      },
    );
  }

  return (
    <main className="auth-page">
      <div className="card auth-card">
        <Logo />
        <h1>Sign in</h1>
        <form onSubmit={onSubmit} className="stack">
          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="username"
              required
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
              }}
            />
          </div>
          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
              }}
            />
          </div>
          {signIn.error && (
            <p role="alert" className="notice notice-danger">
              <AlertIcon />
              <span>{signInErrorMessage(signIn.error)}</span>
            </p>
          )}
          <button type="submit" className="btn btn-primary" disabled={signIn.isPending}>
            {signIn.isPending ? "Signing in" : "Sign in"}
          </button>
        </form>
      </div>
    </main>
  );
}

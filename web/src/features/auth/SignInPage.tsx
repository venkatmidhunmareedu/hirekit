import { useNavigate } from "@tanstack/react-router";
import { CircleAlert, Eye, EyeOff, Lock, Mail, ShieldCheck, TextQuote, Users } from "lucide-react";
import { MotionConfig, motion } from "motion/react";
import { type SubmitEvent, useEffect, useRef, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { Logo } from "../../components/Logo";

import { signInErrorMessage, useLogin } from "./hooks";

const PRINCIPLES = [
  { icon: Users, text: "People decide. The model only proposes scores." },
  {
    icon: TextQuote,
    text: "Every score points to a quote found in the resume, or says no evidence found.",
  },
  {
    icon: ShieldCheck,
    text: "The model sees anonymized text only. Anonymization is a floor, not proof of fairness.",
  },
];

/** The deep brand panel: wordmark, the promise and the three principles. Compact below lg. */
function BrandPanel() {
  return (
    <aside className="flex flex-col gap-10 bg-brand px-6 py-6 text-brand-foreground lg:w-1/2 lg:justify-between lg:px-14 lg:py-14">
      <Logo inverse />
      <p className="text-sm text-balance text-brand-foreground/85 lg:hidden">
        Scores you can defend, with the evidence beside them.
      </p>
      <div className="hidden max-w-lg flex-col gap-10 lg:flex">
        <p className="font-display text-5xl leading-tight font-medium tracking-tight text-balance">
          Scores you can defend, with the evidence beside them.
        </p>
        <ul className="flex flex-col gap-5">
          {PRINCIPLES.map(({ icon: Icon, text }) => (
            <li key={text} className="flex items-start gap-3 text-base text-brand-foreground/85">
              <Icon aria-hidden="true" className="mt-0.5 size-5 shrink-0" />
              {text}
            </li>
          ))}
        </ul>
      </div>
    </aside>
  );
}

/** Sign-in screen: brand panel beside the form at lg and up, one primary action (Design.md 7.1). */
export function SignInPage() {
  const navigate = useNavigate();
  const signIn = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [shown, setShown] = useState(false);
  const emailRef = useRef<HTMLInputElement>(null);
  const Reveal = shown ? EyeOff : Eye;

  // The email field takes focus on arrival, so a keyboard user can type at once.
  useEffect(() => {
    emailRef.current?.focus();
  }, []);

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
    <MotionConfig reducedMotion="user">
      <main className="flex min-h-svh flex-col lg:flex-row">
        <BrandPanel />
        <div className="flex flex-1 items-start justify-center px-6 py-10 lg:items-center">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, ease: "easeOut" }}
            className="flex w-full max-w-sm flex-col gap-8"
          >
            <div className="flex flex-col gap-2">
              <h1 className="font-display text-4xl font-medium">Sign in</h1>
              <p className="text-muted-foreground">Use the account your recruiter set up.</p>
            </div>
            <form onSubmit={onSubmit} className="flex flex-col gap-5">
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="email">Email</Label>
                <div className="relative">
                  <Mail
                    aria-hidden="true"
                    className="pointer-events-none absolute top-3 left-3 size-4 text-muted-foreground"
                  />
                  <Input
                    id="email"
                    name="email"
                    type="email"
                    autoComplete="username"
                    ref={emailRef}
                    required
                    className="h-10 pl-9"
                    value={email}
                    onChange={(e) => {
                      setEmail(e.target.value);
                    }}
                  />
                </div>
              </div>
              <div className="flex flex-col gap-1.5">
                <Label htmlFor="password">Password</Label>
                <div className="relative">
                  <Lock
                    aria-hidden="true"
                    className="pointer-events-none absolute top-3 left-3 size-4 text-muted-foreground"
                  />
                  <Input
                    id="password"
                    name="password"
                    type={shown ? "text" : "password"}
                    autoComplete="current-password"
                    required
                    className="h-10 pr-11 pl-9"
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value);
                    }}
                  />
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    className="absolute top-0 right-0 size-10 text-muted-foreground"
                    aria-label={shown ? "Hide password" : "Show password"}
                    aria-pressed={shown}
                    onClick={() => {
                      setShown(!shown);
                    }}
                  >
                    <Reveal aria-hidden="true" />
                  </Button>
                </div>
              </div>
              {signIn.error && (
                <Alert
                  variant="destructive"
                  className="flex items-center gap-2 border-bad bg-bad-soft"
                >
                  <CircleAlert aria-hidden="true" className="size-4" />
                  <AlertDescription className="text-bad">
                    {signInErrorMessage(signIn.error)}
                  </AlertDescription>
                </Alert>
              )}
              <Button type="submit" size="lg" className="h-11" disabled={signIn.isPending}>
                {signIn.isPending ? "Signing in" : "Sign in"}
              </Button>
            </form>
          </motion.div>
        </div>
      </main>
    </MotionConfig>
  );
}

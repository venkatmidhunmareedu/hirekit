import { useNavigate } from "@tanstack/react-router";
import { CircleAlert } from "lucide-react";
import { type SubmitEvent, useState } from "react";

import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

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
    <main className="flex min-h-screen items-center justify-center px-4 py-10">
      <Card className="w-full max-w-sm py-6">
        <CardHeader className="gap-4">
          <Logo />
          <h1 className="font-display text-3xl font-medium">Sign in</h1>
          <CardDescription>
            Evidence-backed resume screening. People make every decision.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={onSubmit} className="flex flex-col gap-4">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                name="email"
                type="email"
                autoComplete="username"
                required
                className="h-10"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value);
                }}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                className="h-10"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value);
                }}
              />
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
            <Button type="submit" size="lg" className="h-10" disabled={signIn.isPending}>
              {signIn.isPending ? "Signing in" : "Sign in"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import UserLoginCard from "~/components/UserLoginCard";
import { setCurrentUser } from "~/lib/auth";

interface User {
  id: string;
  name: string;
  email: string;
}

export default function LoginPage() {
  const router = useRouter();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("http://localhost:8000/users/")
      .then((r) => {
        if (!r.ok) throw new Error("Failed to fetch users");
        return r.json();
      })
      .then((data: User[]) => setUsers(data))
      .catch(() => setError("Could not load users. Make sure the backend is running."))
      .finally(() => setLoading(false));
  }, []);

  function handleLogin(user: User) {
    setCurrentUser({ id: user.id, name: user.name });
    router.replace("/store");
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-md">
        <h1 className="text-3xl font-bold text-center text-gray-900 mb-2">
          Welcome
        </h1>
        <p className="text-center text-gray-500 mb-8">Select your account to continue</p>

        {loading && (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 bg-gray-200 rounded-xl animate-pulse" />
            ))}
          </div>
        )}

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 rounded-xl p-4 text-sm text-center">
            {error}
          </div>
        )}

        {!loading && !error && (
          <div className="space-y-3">
            {users.map((user) => (
              <UserLoginCard
                key={user.id}
                id={user.id}
                name={user.name}
                email={user.email}
                onClick={() => handleLogin(user)}
              />
            ))}
          </div>
        )}
      </div>
    </main>
  );
}

"use client";

interface UserLoginCardProps {
  id: string;
  name: string;
  email: string;
  onClick: () => void;
}

export default function UserLoginCard({ name, email, onClick }: UserLoginCardProps) {
  return (
    <button
      onClick={onClick}
      className="w-full text-left bg-white rounded-xl shadow-md hover:shadow-lg hover:ring-2 hover:ring-blue-500 transition-all duration-150 p-6 border border-gray-200 cursor-pointer"
    >
      <h3 className="text-lg font-semibold text-gray-900">{name}</h3>
      <p className="text-sm text-gray-500 mt-1">{email}</p>
    </button>
  );
}

import { Sun, Moon } from "lucide-react";

export function ThemeToggle({ theme, toggleTheme }) {
  return (
    <button
      data-testid="theme-toggle-btn"
      onClick={toggleTheme}
      className="p-2 rounded-md hover:bg-accent transition-colors duration-200"
      title={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
    >
      {theme === 'dark' ? (
        <Sun className="w-4 h-4 text-muted-foreground" />
      ) : (
        <Moon className="w-4 h-4 text-muted-foreground" />
      )}
    </button>
  );
}

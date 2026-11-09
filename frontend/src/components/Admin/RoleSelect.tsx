import type { Role } from "@/client"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ROLE_OPTIONS, roleLabel } from "@/lib/roles"

interface RoleSelectProps {
  value: Role
  onChange: (role: Role) => void
}

export const RoleSelect = ({ value, onChange }: RoleSelectProps) => (
  <Select value={value} onValueChange={(v) => onChange(v as Role)}>
    <SelectTrigger className="w-full" data-testid="role-select">
      <SelectValue placeholder="Select a role" />
    </SelectTrigger>
    <SelectContent>
      {ROLE_OPTIONS.map((role) => (
        <SelectItem key={role} value={role}>
          {roleLabel(role)}
        </SelectItem>
      ))}
    </SelectContent>
  </Select>
)

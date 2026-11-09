import { useQuery } from "@tanstack/react-query"

import { type UserMePublic, UsersService } from "@/client"

export const isLoggedIn = () => {
  return localStorage.getItem("access_token") !== null
}

const useCurrentUser = () =>
  useQuery<UserMePublic | null, Error>({
    queryKey: ["currentUser"],
    queryFn: async () => (await UsersService.readUserMe()).data,
    enabled: isLoggedIn(),
  })

export default useCurrentUser

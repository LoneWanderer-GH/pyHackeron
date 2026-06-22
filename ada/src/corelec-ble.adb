--  corelec-ble.adb
--  Corps du service BLE haut-niveau : délègue au backend C (corelec_ble_backend_t).

with Ada.Unchecked_Deallocation;
with System;

package body Corelec.BLE is
   use type System.Address;

   --  ── Imports C (corelec_ble_backend.h) ───────────────────────────────────

   function C_Backend_Create
     (Kind            : Backend_Kind;
      Address         : Interfaces.C.char_array;
      Timeout_Seconds : Interfaces.C.unsigned;
      On_Status       : Status_Callback;
      On_Notification : Notification_Callback) return System.Address
   with Import => True, Convention => C,
        External_Name => "corelec_ble_backend_create";

   procedure C_Backend_Destroy (Handle : System.Address)
   with Import => True, Convention => C,
        External_Name => "corelec_ble_backend_destroy";

   function C_Backend_Connect (Handle : System.Address) return Interfaces.C.int
   with Import => True, Convention => C,
        External_Name => "corelec_ble_backend_connect";

   function C_Backend_Disconnect (Handle : System.Address) return Interfaces.C.int
   with Import => True, Convention => C,
        External_Name => "corelec_ble_backend_disconnect";

   function C_Backend_Restart (Handle : System.Address) return Interfaces.C.int
   with Import => True, Convention => C,
        External_Name => "corelec_ble_backend_restart";

   function C_Backend_Poll (Handle : System.Address) return Interfaces.C.int
   with Import => True, Convention => C,
        External_Name => "corelec_ble_backend_poll";

   --  ── Helpers ─────────────────────────────────────────────────────────────

   procedure Free is new Ada.Unchecked_Deallocation (Service_Handle, Service_Handle_Access);

   --  ── Implémentation ──────────────────────────────────────────────────────

   function Create
     (Backend       : Backend_Kind;
      Address       : Interfaces.C.char_array;
      Timeout_Sec   : Interfaces.C.unsigned;
      On_Status     : Status_Callback := null;
      On_Notify     : Notification_Callback := null) return Service_Handle_Access
   is
      H : Service_Handle_Access := new Service_Handle;
   begin
      H.Backend     := Backend;
      H.Timeout_Sec := Timeout_Sec;
      H.On_Status   := On_Status;
      H.On_Notify   := On_Notify;
      --  Le backend C copie l'adresse en interne ; on passe Address directement.
      H.C_Handle := C_Backend_Create
        (Backend, Address, Timeout_Sec, On_Status, On_Notify);
      return H;
   end Create;

   procedure Destroy (Handle : in out Service_Handle_Access) is
   begin
      if Handle /= null then
         if Handle.C_Handle /= System.Null_Address then
            C_Backend_Destroy (Handle.C_Handle);
            Handle.C_Handle := System.Null_Address;
         end if;
         Free (Handle);
      end if;
   end Destroy;

   procedure Connect (Handle : in out Service_Handle) is
      Unused : Interfaces.C.int;
      pragma Unreferenced (Unused);
   begin
      if Handle.C_Handle /= System.Null_Address then
         Unused := C_Backend_Connect (Handle.C_Handle);
      end if;
   end Connect;

   procedure Disconnect (Handle : in out Service_Handle) is
      Unused : Interfaces.C.int;
      pragma Unreferenced (Unused);
   begin
      if Handle.C_Handle /= System.Null_Address then
         Unused := C_Backend_Disconnect (Handle.C_Handle);
      end if;
   end Disconnect;

   procedure Request_Restart (Handle : in out Service_Handle) is
      Unused : Interfaces.C.int;
      pragma Unreferenced (Unused);
   begin
      if Handle.C_Handle /= System.Null_Address then
         Unused := C_Backend_Restart (Handle.C_Handle);
      end if;
   end Request_Restart;

   procedure Poll (Handle : in out Service_Handle) is
      Unused : Interfaces.C.int;
      pragma Unreferenced (Unused);
   begin
      if Handle.C_Handle /= System.Null_Address then
         Unused := C_Backend_Poll (Handle.C_Handle);
      end if;
   end Poll;

end Corelec.BLE;


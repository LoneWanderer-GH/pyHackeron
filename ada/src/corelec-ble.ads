with Corelec.Types;
with Interfaces.C;

package Corelec.BLE is
   pragma Preelaborate;

   type Backend_Kind is
     (Backend_None,
      Backend_Portable_C,
      Backend_BlueZ_C,
      Backend_WinRT_C,
      Backend_NimBLE_C,
      Backend_BTstack_C)
     with Convention => C;

   type BLE_Event_Kind is
     (Event_None,
      Event_Connecting,
      Event_Connected,
      Event_Disconnected,
      Event_Error,
      Event_Notification)
     with Convention => C;

   type Notification_Callback is access procedure
     (Frame  : access constant Corelec.Types.Frame_Array;
      Length : Interfaces.C.unsigned)
     with Convention => C;

   type Status_Callback is access procedure
     (Info : access constant Corelec.Types.Connection_Info)
     with Convention => C;

   type Service_Handle is limited private;
   type Service_Handle_Access is access all Service_Handle;

   function Create
     (Backend       : Backend_Kind;
      Address       : Interfaces.C.char_array;
      Timeout_Sec   : Interfaces.C.unsigned;
      On_Status     : Status_Callback := null;
      On_Notify     : Notification_Callback := null) return Service_Handle_Access;

   procedure Destroy (Handle : in out Service_Handle_Access);
   procedure Connect (Handle : in out Service_Handle);
   procedure Disconnect (Handle : in out Service_Handle);
   procedure Request_Restart (Handle : in out Service_Handle);
   procedure Poll (Handle : in out Service_Handle);

 private
   type Service_Handle is limited record
      Backend     : Backend_Kind := Backend_None;
      Address     : Interfaces.C.char_array (0 .. 63) := (others => Interfaces.C.nul);
      Timeout_Sec : Interfaces.C.unsigned := 120;
      On_Status   : Status_Callback := null;
      On_Notify   : Notification_Callback := null;
   end record;
end Corelec.BLE;
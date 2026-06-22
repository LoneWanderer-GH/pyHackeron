with Corelec.Types;
with Interfaces.C;
with System;

package Corelec.BLE is
   pragma Preelaborate;

   --  Doit correspondre exactement à corelec_ble_backend_kind_t dans corelec_ble_backend.h
   type Backend_Kind is
     (Backend_None,      --  0 CORELEC_BLE_BACKEND_NONE
      Backend_BlueZ_C,   --  1 CORELEC_BLE_BACKEND_BLUEZ
      Backend_WinRT_C,   --  2 CORELEC_BLE_BACKEND_WINRT
      Backend_NimBLE_C,  --  3 CORELEC_BLE_BACKEND_NIMBLE
      Backend_BTstack_C) --  4 CORELEC_BLE_BACKEND_BTSTACK
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
      C_Handle    : System.Address := System.Null_Address;  --  corelec_ble_backend_t *
   end record;
end Corelec.BLE;
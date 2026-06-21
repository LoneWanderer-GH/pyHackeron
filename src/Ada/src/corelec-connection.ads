with Corelec.Types;
with Interfaces.C;

package Corelec.Connection is
   type Connection_Manager is tagged private;
   type Connection_Manager_Access is access all Connection_Manager;

   function Create
     (Timeout_Seconds    : Interfaces.C.unsigned := 120;
      Initial_Retry_Count : Interfaces.C.unsigned := 0) return Connection_Manager_Access;
   procedure Destroy (Handle : in out Connection_Manager_Access);

   procedure Begin_Connect (Handle : in out Connection_Manager);
   procedure Tick_Connecting (Handle : in out Connection_Manager; Elapsed_Seconds : Interfaces.C.unsigned);
   procedure Mark_Connected (Handle : in out Connection_Manager; Elapsed_Seconds : Interfaces.C.unsigned);
   procedure Mark_Error (Handle : in out Connection_Manager; Message : String; Elapsed_Seconds : Interfaces.C.unsigned);
   procedure Mark_Disconnected (Handle : in out Connection_Manager; Message : String := "Disconnected");
   procedure Request_Restart (Handle : in out Connection_Manager);
   procedure Request_Cancel (Handle : in out Connection_Manager);

   function Info (Handle : Connection_Manager) return Corelec.Types.Connection_Info;

 private
   type Connection_Manager is tagged record
      Data : Corelec.Types.Connection_Info;
   end record;
end Corelec.Connection;

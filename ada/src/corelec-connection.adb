with Ada.Unchecked_Deallocation;
with Interfaces.C;
with Interfaces.C.Extensions;

package body Corelec.Connection is
   procedure Free is new Ada.Unchecked_Deallocation (Connection_Manager, Connection_Manager_Access);

   procedure Set_Message (Target : out Corelec.Types.Message_Buffer; Value : String) is
      Last : constant Natural := Natural'Min (Value'Length, Target'Length - 1);
   begin
      Target := (others => Character'Val (0));
      for I in 0 .. Last - 1 loop
         Target (I) := Value (Value'First + I);
      end loop;
   end Set_Message;

   function Create
     (Timeout_Seconds    : Interfaces.C.unsigned := 120;
      Initial_Retry_Count : Interfaces.C.unsigned := 0) return Connection_Manager_Access
   is
      Handle : constant Connection_Manager_Access := new Connection_Manager;
   begin
      Handle.Data.Timeout := Timeout_Seconds;
      Handle.Data.Remaining := Timeout_Seconds;
      Handle.Data.Retry_Count := Initial_Retry_Count;
      Set_Message (Handle.Data.Message, "Disconnected");
      return Handle;
   end Create;

   procedure Destroy (Handle : in out Connection_Manager_Access) is
   begin
      if Handle /= null then
         Free (Handle);
      end if;
   end Destroy;

   procedure Begin_Connect (Handle : in out Connection_Manager) is
   begin
      Handle.Data.State := Corelec.Types.State_Connecting;
      Handle.Data.Elapsed := 0;
      Handle.Data.Remaining := Handle.Data.Timeout;
      Handle.Data.Should_Retry := 0;
      Handle.Data.Stop_Requested := 0;
      Set_Message (Handle.Data.Message, "Connecting");
   end Begin_Connect;

   procedure Tick_Connecting (Handle : in out Connection_Manager; Elapsed_Seconds : Interfaces.C.unsigned) is
      use type Interfaces.C.unsigned;
   begin
      Handle.Data.State := Corelec.Types.State_Connecting;
      Handle.Data.Elapsed := Elapsed_Seconds;
      if Elapsed_Seconds < Handle.Data.Timeout then
         Handle.Data.Remaining := Handle.Data.Timeout - Elapsed_Seconds;
      else
         Handle.Data.Remaining := 0;
      end if;
   end Tick_Connecting;

   procedure Mark_Connected (Handle : in out Connection_Manager; Elapsed_Seconds : Interfaces.C.unsigned) is
      use type Interfaces.C.unsigned;
   begin
      Handle.Data.State := Corelec.Types.State_Connected;
      Handle.Data.Elapsed := Elapsed_Seconds;
      if Elapsed_Seconds < Handle.Data.Timeout then
         Handle.Data.Remaining := Handle.Data.Timeout - Elapsed_Seconds;
      else
         Handle.Data.Remaining := 0;
      end if;
      Handle.Data.Should_Retry := 0;
      Set_Message (Handle.Data.Message, "Connected");
   end Mark_Connected;

   procedure Mark_Error (Handle : in out Connection_Manager; Message : String; Elapsed_Seconds : Interfaces.C.unsigned) is
      use type Interfaces.C.unsigned;
      use type Interfaces.C.Extensions.Unsigned_8;
   begin
      Handle.Data.State := Corelec.Types.State_Error;
      Handle.Data.Elapsed := Elapsed_Seconds;
      if Elapsed_Seconds < Handle.Data.Timeout then
         Handle.Data.Remaining := Handle.Data.Timeout - Elapsed_Seconds;
      else
         Handle.Data.Remaining := 0;
      end if;
      Handle.Data.Should_Retry := (if Handle.Data.Stop_Requested = 0 then 1 else 0);
      Set_Message (Handle.Data.Message, Message);
   end Mark_Error;

   procedure Mark_Disconnected (Handle : in out Connection_Manager; Message : String := "Disconnected") is
   begin
      Handle.Data.State := Corelec.Types.State_Disconnected;
      Handle.Data.Elapsed := 0;
      Handle.Data.Remaining := Handle.Data.Timeout;
      Set_Message (Handle.Data.Message, Message);
   end Mark_Disconnected;

   procedure Request_Restart (Handle : in out Connection_Manager) is
      use type Interfaces.C.unsigned;
   begin
      Handle.Data.Stop_Requested := 1;
      Handle.Data.Should_Retry := 1;
      Handle.Data.Retry_Count := Handle.Data.Retry_Count + 1;
      Set_Message (Handle.Data.Message, "Restart requested");
   end Request_Restart;

   procedure Request_Cancel (Handle : in out Connection_Manager) is
   begin
      Handle.Data.Stop_Requested := 1;
      Handle.Data.Should_Retry := 0;
      Set_Message (Handle.Data.Message, "Cancel requested");
   end Request_Cancel;

   function Info (Handle : Connection_Manager) return Corelec.Types.Connection_Info is
   begin
      return Handle.Data;
   end Info;
end Corelec.Connection;

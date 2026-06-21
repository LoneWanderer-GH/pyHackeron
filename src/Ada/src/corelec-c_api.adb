with Corelec.Connection;
with Corelec.Decoder;
with Corelec.Protocol;
with Interfaces.C.Strings;

package body Corelec.C_API is
   function To_Ada (Value : Interfaces.C.char_array) return String is
   begin
      return Interfaces.C.To_Ada (Value);
   end To_Ada;

   function Connection_Manager_Create
     (Timeout_Seconds     : Interfaces.C.unsigned;
      Initial_Retry_Count : Interfaces.C.unsigned) return Connection_Manager_Handle
   is
   begin
      return Connection_Manager_Handle (Corelec.Connection.Create (Timeout_Seconds, Initial_Retry_Count));
   end Connection_Manager_Create;

   procedure Connection_Manager_Destroy
     (Handle : in out Connection_Manager_Handle) is
      Tmp : Corelec.Connection.Connection_Manager_Access := Corelec.Connection.Connection_Manager_Access (Handle);
   begin
      Corelec.Connection.Destroy (Tmp);
      Handle := null;
   end Connection_Manager_Destroy;

   procedure Connection_Manager_Begin_Connect
     (Handle : Connection_Manager_Handle) is
   begin
      if Handle /= null then
         Corelec.Connection.Begin_Connect (Handle.all);
      end if;
   end Connection_Manager_Begin_Connect;

   procedure Connection_Manager_Tick_Connecting
     (Handle : Connection_Manager_Handle;
      Elapsed_Seconds : Interfaces.C.unsigned) is
   begin
      if Handle /= null then
         Corelec.Connection.Tick_Connecting (Handle.all, Elapsed_Seconds);
      end if;
   end Connection_Manager_Tick_Connecting;

   procedure Connection_Manager_Mark_Connected
     (Handle : Connection_Manager_Handle;
      Elapsed_Seconds : Interfaces.C.unsigned) is
   begin
      if Handle /= null then
         Corelec.Connection.Mark_Connected (Handle.all, Elapsed_Seconds);
      end if;
   end Connection_Manager_Mark_Connected;

   procedure Connection_Manager_Mark_Error
     (Handle : Connection_Manager_Handle;
      Message : Interfaces.C.char_array;
      Elapsed_Seconds : Interfaces.C.unsigned) is
   begin
      if Handle /= null then
         Corelec.Connection.Mark_Error (Handle.all, To_Ada (Message), Elapsed_Seconds);
      end if;
   end Connection_Manager_Mark_Error;

   procedure Connection_Manager_Mark_Disconnected
     (Handle : Connection_Manager_Handle;
      Message : Interfaces.C.char_array) is
   begin
      if Handle /= null then
         Corelec.Connection.Mark_Disconnected (Handle.all, To_Ada (Message));
      end if;
   end Connection_Manager_Mark_Disconnected;

   procedure Connection_Manager_Request_Restart
     (Handle : Connection_Manager_Handle) is
   begin
      if Handle /= null then
         Corelec.Connection.Request_Restart (Handle.all);
      end if;
   end Connection_Manager_Request_Restart;

   procedure Connection_Manager_Request_Cancel
     (Handle : Connection_Manager_Handle) is
   begin
      if Handle /= null then
         Corelec.Connection.Request_Cancel (Handle.all);
      end if;
   end Connection_Manager_Request_Cancel;

   function Connection_Manager_Get_Info
     (Handle : Connection_Manager_Handle) return Corelec.Types.Connection_Info is
   begin
      if Handle = null then
         return (others => <>);
      end if;
      return Corelec.Connection.Info (Handle.all);
   end Connection_Manager_Get_Info;

   function CRC_Frame
     (Raw : Corelec.Types.Frame_Array;
      Count : Interfaces.C.unsigned) return Corelec.Types.U8 is
   begin
      return Corelec.Protocol.CRC (Raw, Natural (Count));
   end CRC_Frame;

   procedure Build_Ask
     (Cmd : Corelec.Types.U8;
      Packet : out Corelec.Types.Frame_Array) is
   begin
      Corelec.Protocol.Build_Ask (Cmd, Packet);
   end Build_Ask;

   function Parse_Frame
     (Raw : Corelec.Types.Frame_Array;
      Out_Frame : access Corelec.Types.Frame_Type) return Interfaces.C.int is
      Parsed : Corelec.Types.Frame_Type;
   begin
      if Out_Frame = null then
         return 0;
      end if;

      if Corelec.Protocol.Parse_Frame (Raw, Parsed) then
         Out_Frame.all := Parsed;
         return 1;
      end if;
      return 0;
   end Parse_Frame;

   procedure Decode_Frame
     (Frame : access constant Corelec.Types.Frame_Type;
      Out_D : access Corelec.Types.Decoded_Frame) is
   begin
      if Frame = null or else Out_D = null then
         return;
      end if;
      Corelec.Decoder.Decode_Frame (Frame.all, Out_D.all);
   end Decode_Frame;
end Corelec.C_API;

with Corelec.Connection;
with Corelec.Types;
with Interfaces.C;

package Corelec.C_API is
   pragma Elaborate_Body;

   type Connection_Manager_Handle is access all Corelec.Connection.Connection_Manager
     with Convention => C;

   function Connection_Manager_Create
     (Timeout_Seconds     : Interfaces.C.unsigned;
      Initial_Retry_Count : Interfaces.C.unsigned) return Connection_Manager_Handle
     with Export => True, Convention => C, External_Name => "corelec_connection_manager_create";

   procedure Connection_Manager_Destroy
     (Handle : in out Connection_Manager_Handle)
     with Export => True, Convention => C, External_Name => "corelec_connection_manager_destroy";

   procedure Connection_Manager_Begin_Connect
     (Handle : Connection_Manager_Handle)
     with Export => True, Convention => C, External_Name => "corelec_connection_manager_begin_connect";

   procedure Connection_Manager_Tick_Connecting
     (Handle : Connection_Manager_Handle;
      Elapsed_Seconds : Interfaces.C.unsigned)
     with Export => True, Convention => C, External_Name => "corelec_connection_manager_tick_connecting";

   procedure Connection_Manager_Mark_Connected
     (Handle : Connection_Manager_Handle;
      Elapsed_Seconds : Interfaces.C.unsigned)
     with Export => True, Convention => C, External_Name => "corelec_connection_manager_mark_connected";

   procedure Connection_Manager_Mark_Error
     (Handle : Connection_Manager_Handle;
      Message : Interfaces.C.char_array;
      Elapsed_Seconds : Interfaces.C.unsigned)
     with Export => True, Convention => C, External_Name => "corelec_connection_manager_mark_error";

   procedure Connection_Manager_Mark_Disconnected
     (Handle : Connection_Manager_Handle;
      Message : Interfaces.C.char_array)
     with Export => True, Convention => C, External_Name => "corelec_connection_manager_mark_disconnected";

   procedure Connection_Manager_Request_Restart
     (Handle : Connection_Manager_Handle)
     with Export => True, Convention => C, External_Name => "corelec_connection_manager_request_restart";

   procedure Connection_Manager_Request_Cancel
     (Handle : Connection_Manager_Handle)
     with Export => True, Convention => C, External_Name => "corelec_connection_manager_request_cancel";

   function Connection_Manager_Get_Info
     (Handle : Connection_Manager_Handle) return Corelec.Types.Connection_Info
     with Export => True, Convention => C, External_Name => "corelec_connection_manager_get_info";

   function CRC_Frame
     (Raw : Corelec.Types.Frame_Array;
      Count : Interfaces.C.unsigned) return Corelec.Types.U8
     with Export => True, Convention => C, External_Name => "corelec_crc_frame";

   procedure Build_Ask
     (Cmd : Corelec.Types.U8;
      Packet : out Corelec.Types.Frame_Array)
     with Export => True, Convention => C, External_Name => "corelec_build_ask";

   function Parse_Frame
     (Raw : Corelec.Types.Frame_Array;
      Out_Frame : access Corelec.Types.Frame_Type) return Interfaces.C.int
     with Export => True, Convention => C, External_Name => "corelec_parse_frame";

   procedure Decode_Frame
     (Frame : access constant Corelec.Types.Frame_Type;
      Out_D : access Corelec.Types.Decoded_Frame)
     with Export => True, Convention => C, External_Name => "corelec_decode_frame";
end Corelec.C_API;
